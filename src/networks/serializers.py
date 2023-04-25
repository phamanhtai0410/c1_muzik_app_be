from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers

from src.networks.models import Network
from src.rates.serializers import CurrencySerializer


class NetworkSerializer(serializers.ModelSerializer):
    currencies = serializers.SerializerMethodField()

    class Meta:
        model = Network
        fields = (
            "ipfs_icon",
            "name",
            "short_name",
            "native_symbol",
            "exchange_address",
            "fabric721_address",
            "fabric1155_address",
            "promotion_address",
            "platform_fee_percentage",
            "currencies",
        )
        lookup_field = "name"

    @swagger_serializer_method(serializer_or_field=CurrencySerializer(many=True))
    def get_currencies(self, obj):
        return CurrencySerializer(obj.currencies.all(), many=True).data
