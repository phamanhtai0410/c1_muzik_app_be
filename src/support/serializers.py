from rest_framework import serializers

from src.support.models import Config


class ConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config
        fields = ("max_royalty_percentage","top_collections_period")
