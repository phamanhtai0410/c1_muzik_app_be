from rest_framework import serializers

from src.mail_subscription.models import SubscriptionUser


class SubscriptionUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionUser
        fields = ("email_address",)
