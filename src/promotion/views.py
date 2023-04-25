from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from src.consts import TOKEN_MINT_GAS_LIMIT
from src.promotion.exceptions import PackageNotFound, PromotionExists
from src.promotion.models import Promotion, PromotionOptions, PromotionSettings
from src.promotion.serializers import PromotionSettingsSerializer
from src.rates.api import calculate_amount
from src.rates.exceptions import CurrencyNotFound
from src.rates.models import UsdRate
from src.store.exceptions import OwnershipNotFound, TokenNotFound
from src.store.models import Ownership, Token
from src.utilities import sign_message


class PromotionView(ModelViewSet):
    """Return all supported networks."""

    serializer_class = PromotionSettingsSerializer
    queryset = PromotionSettings.objects.all()
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="promote token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "package": openapi.Schema(type=openapi.TYPE_NUMBER),
                "currency": openapi.Schema(
                    type=openapi.TYPE_STRING, description="payment currency symbol"
                ),
                "token_id": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
            required=["package", "currency", "token_id"],
        ),
        responses={200: "Verification request sent", 400: "Request already sent"},
    )
    def create(self, request):
        request_data = request.data
        package_id = request_data.get("package")
        currency = request_data.get("currency")
        token_id = request_data.get("token_id")
        package = PromotionOptions.objects.filter(package=package_id).first()
        if not package:
            raise PackageNotFound
        token = Token.objects.filter(id=token_id).first()
        if not token:
            raise TokenNotFound
        if package.promotion.network != token.collection.network:
            raise PackageNotFound
        network = token.collection.network
        currency = UsdRate.objects.filter(symbol=currency, network=network).first()
        if not currency:
            raise CurrencyNotFound
        ownership = Ownership.objects.filter(token=token, owner=request.user).first()
        if not ownership:
            raise OwnershipNotFound
        if Promotion.objects.filter(
            token=token,
            owner=ownership,
            status__in=[
                Promotion.PromotionStatus.WAITING,
                Promotion.PromotionStatus.IN_PROGRESS,
            ],
        ).exists():
            raise PromotionExists

        # get data for signature and tx
        price = calculate_amount(package.usd_price, "USD", currency.symbol)
        currency_amount = int(price * currency.get_decimals)
        value = 0
        if currency.address.lower() == token.native_address:
            value = currency_amount
        currency_token = network.wrap_in_checksum(currency.address)
        token_address = network.wrap_in_checksum(token.collection.address)
        deadline_timestamp = int((timezone.now() + network.deadline).timestamp())

        # generate signature
        sign_types = [
            "uint256",
            "address",
            "address",
            "uint256",
            "address",
            "uint256",
            "uint256",
            "address",
            "uint256",
            "uint256",
        ]
        message = [
            network.chain_id,
            network.wrap_in_checksum(request.user.username),
            network.wrap_in_checksum(network.promotion_address),
            package.package,
            currency_token,
            currency_amount,
            token.collection.network.chain_id,  # for future crosschain promotions
            token_address,
            int(token.internal_id),
            deadline_timestamp,
        ]
        signature = sign_message(sign_types, message)

        # construct tx
        args_types = [
            "uint256",
            "address",
            "uint256",
            "uint256",
            "address",
            "uint256",
            "uint256",
            "bytes",
        ]
        args_message = [
            package.package,
            currency_token,
            currency_amount,
            token.collection.network.chain_id,
            token_address,
            int(token.internal_id),
            deadline_timestamp,
            signature,
        ]
        initial_tx = token.collection.network.contract_call(
            method_type="write",
            contract_type="promotion",
            gas_limit=TOKEN_MINT_GAS_LIMIT,
            nonce_username=request.user.username,
            tx_value=value,
            function_name="promote",
            input_params=tuple(args_message),
            input_type=tuple(args_types),
        )
        return Response({"initial_tx": initial_tx}, status=status.HTTP_200_OK)
