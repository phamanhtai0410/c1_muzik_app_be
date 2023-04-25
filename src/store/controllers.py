from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from django.apps import apps
from django.db import transaction

from src.activity.models import TokenHistory
from src.rates.models import UsdRate

if TYPE_CHECKING:
    from src.accounts.models import AdvUser


class TokenController:
    """Class for change token data"""

    def __init__(self, token):
        self.token = token

    def check_is_approved(self, user: "AdvUser"):
        network = self.token.collection.network
        return network.contract_call(
            method_type="read",
            contract_type=f"{self.token.standard.lower()}main",
            address=network.wrap_in_checksum(self.token.collection.address),
            function_name="isApprovedForAll",
            input_params=(
                network.wrap_in_checksum(user.username),
                network.wrap_in_checksum(network.exchange_address),
            ),
            input_type=("address", "address"),
            output_types=("bool",),
        )

    def change_sell_status(self, user: "AdvUser" = None, **kwargs) -> Optional[str]:
        """
        Return dict of errors or None.
        """
        data = {
            "selling": kwargs.get("selling", False),
            "currency": kwargs.get("currency", None),
            "price": kwargs.get("price", None),
            "minimal_bid": kwargs.get("minimal_bid", None),
            "start_auction": kwargs.get("start_auction", None),
            "end_auction": kwargs.get("end_auction", None),
            "amount": kwargs.get("amount", 0),
        }

        try:
            # check nft approval before setting on sale
            if data.get("selling"):
                is_approved = self.check_is_approved(user)
                if not is_approved:
                    return "Token must be approved to exchange contract before putting on sale"

            ownership = self.token.ownerships.get(owner=user)
            ownership.selling = data.get("selling")
            ownership.currency_id = data.get("currency")
            ownership.price = data.get("price")
            ownership.minimal_bid = data.get("minimal_bid")
            ownership.selling_quantity = data.get("amount")
            ownership.start_auction = data.get("start_auction")
            ownership.end_auction = data.get("end_auction")
            ownership.full_clean()
            ownership.save()
        except Exception as e:
            return f"exception: {e}"

        if data.get("selling"):
            # add changes to listing
            TokenHistory.objects.create(
                token=self.token,
                old_owner=user,
                currency_id=data.get("currency"),
                amount=data.get("amount"),
                price=data.get("price") or data.get("minimal_bid"),
                method="Listing",
            )

    def _create_token_instance(self, request, ipfs, media_format):
        self.token.ipfs = ipfs.get("general")
        self.token.image = ipfs.get("image")
        self.token.animation_file = ipfs.get("animation_file")
        self.token.name = request.data.get("name")
        self.token.format = media_format
        self.token.description = request.data.get("description")
        self.token.creator = request.user
        self.token.total_supply = request.data.get("total_supply", 1)
        self.token.digital_key = request.data.get("digital_key")
        self.token.external_link = request.data.get("external_link")

        details = request.data.get("details")
        if details:
            self.token._parse_and_save_details(details)

        category_id = request.data.get("category")
        if category_id:
            category_model = apps.get_model("store", "Category")
            category = category_model.objects.filter(id=category_id).first()
            self.token.category = category

        self.token.full_clean()
        self.token.save()

    def _create_ownership_instance(self, request):
        self.token.owners.add(request.user)
        ownership = self.token.ownerships.first()

        ownership.quantity = request.data.get("total_supply", 1)

        ownership.start_auction = request.data.get("start_auction")
        ownership.end_auction = request.data.get("end_auction")

        price = request.data.get("price")
        price = Decimal(price) if price else None
        ownership.price = price

        minimal_bid = request.data.get("minimal_bid")
        minimal_bid = Decimal(minimal_bid) if minimal_bid else None
        ownership.minimal_bid = minimal_bid

        selling = request.data.get("selling", "false").lower() == "true"
        ownership.selling = selling

        currency_symbol = request.data.get("currency")
        if currency_symbol:
            currency = (
                UsdRate.objects.filter(symbol__iexact=currency_symbol)
                .filter(network=self.token.collection.network)
                .first()
            )
            if currency:
                ownership.currency = currency

        ownership.selling_quantity = request.data.get(
            "selling_quantity", 1 if selling else 0
        )

        ownership.full_clean()
        ownership.save()

    @transaction.atomic
    def save_in_db(self, request, ipfs, media_format):
        self._create_token_instance(request, ipfs, media_format)
        self._create_ownership_instance(request)
