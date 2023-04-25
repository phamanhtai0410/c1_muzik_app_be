from rest_framework import serializers

from src.networks.serializers import NetworkSerializer
from src.promotion.models import Promotion, PromotionOptions, PromotionSettings


class PromotionOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromotionOptions
        fields = ("days", "usd_price", "package")


class PromotionSettingsSerializer(serializers.ModelSerializer):
    options = PromotionOptionsSerializer(many=True)
    network = NetworkSerializer()

    class Meta:
        model = PromotionSettings
        fields = ("slots", "available_slots", "network", "options")


class PromotionSerializer(serializers.ModelSerializer):
    queue = serializers.SerializerMethodField()

    class Meta:
        model = Promotion
        fields = ("id", "valid_until", "queue", "status")

    def get_queue(self, obj) -> int:
        return Promotion.objects.filter(
            status=Promotion.PromotionStatus.WAITING, id__lt=obj.id
        ).count()


class PromotionSlimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = ("id",)
