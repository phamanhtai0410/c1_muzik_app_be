from rest_framework import serializers

from src.rates.models import UsdRate


class CurrencySerializer(serializers.ModelSerializer):
    network = serializers.CharField(source="network.name")

    class Meta:
        model = UsdRate
        fields = (
            "rate",
            "symbol",
            "name",
            "image",
            "address",
            "network"
        )
