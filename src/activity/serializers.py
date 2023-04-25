from rest_framework import serializers

from src.accounts.serializers import UserSlimSerializer
from src.activity.models import ActivitySubscription, CollectionStat, UserStat
from src.utilities import PaginateSerializer


class UserStatSerializer(serializers.ModelSerializer):
    user = UserSlimSerializer()

    class Meta:
        model = UserStat
        fields = (
            "id",
            "user",
            "amount",
        )


class ActivitySerializer(serializers.ModelSerializer):
    token_id = serializers.SerializerMethodField()
    token_image = serializers.SerializerMethodField()
    token_name = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    from_id = serializers.SerializerMethodField()
    from_image = serializers.SerializerMethodField()
    from_address = serializers.SerializerMethodField()
    from_name = serializers.SerializerMethodField()
    to_id = serializers.SerializerMethodField()
    to_image = serializers.SerializerMethodField()
    to_address = serializers.SerializerMethodField()
    to_name = serializers.SerializerMethodField()
    tx_hash = serializers.SerializerMethodField()

    class Meta:
        model = ActivitySubscription
        fields = (
            "token_id",
            "token_image",
            "token_name",
            "currency",
            "amount",
            "price",
            "from_id",
            "from_image",
            "from_address",
            "from_name",
            "to_id",
            "to_image",
            "to_address",
            "to_name",
            "method",
            "date",
            "id",
            "is_viewed",
            "tx_hash",
        )

    def _get_user_from(self, obj):
        try:
            user_from = getattr(obj.activity, "user")
        except AttributeError:
            user_from = getattr(obj.activity, "old_owner")
        return user_from

    def _get_user_to(self, obj):
        try:
            user_to = getattr(obj.activity, "whom_follow")
        except AttributeError:
            try:
                user_to = getattr(obj.activity, "new_owner")
            except AttributeError:
                user_to = None
        return user_to

    def get_token_id(self, obj):
        if obj.activity.token:
            return obj.activity.token.id
        return None

    def get_token_image(self, obj):
        if obj.activity.token:
            return obj.activity.token.image
        return None

    def get_token_name(self, obj):
        if obj.activity.token:
            return obj.activity.token.name
        return None

    def get_currency(self, obj):
        if hasattr(obj.activity, "currency"):
            currency = obj.activity.currency.symbol if obj.activity.currency else None
            return currency

    def get_amount(self, obj):
        try:
            amount = getattr(obj.activity, "amount")
        except AttributeError:
            amount = None
        return amount

    def get_price(self, obj):
        try:
            price = getattr(obj.activity, "price")
        except AttributeError:
            price = ""
        return price

    def get_from_id(self, obj):
        user_from = self._get_user_from(obj)
        if user_from:
            return user_from.url
        return None

    def get_from_image(self, obj):
        user_from = self._get_user_from(obj)
        if user_from:
            return user_from.avatar
        return None

    def get_from_address(self, obj):
        user_from = self._get_user_from(obj)
        if user_from:
            return user_from.username
        return None

    def get_from_name(self, obj):
        user_from = self._get_user_from(obj)
        if user_from:
            return user_from.get_name()
        return None

    def get_to_id(self, obj):
        user_to = self._get_user_to(obj)
        if user_to:
            return user_to.url
        return None

    def get_to_image(self, obj):
        user_to = self._get_user_to(obj)
        if user_to:
            return user_to.avatar
        return None

    def get_to_address(self, obj):
        user_to = self._get_user_to(obj)
        if user_to:
            return user_to.username
        return None

    def get_to_name(self, obj):
        user_to = self._get_user_to(obj)
        if user_to:
            return user_to.get_name()
        return None

    def get_tx_hash(self, obj):
        try:
            return obj.activity.tx_hash
        except AttributeError:
            return None



class CollectionStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectionStat
        fields = (
            "date",
            "amount",
            "average_price",
            "number_of_trades",
        )


class CollectionTradeDataSerializer(serializers.Serializer):
    volume = serializers.CharField(max_length=200)
    avg_price = serializers.CharField(max_length=200)


class PaginateActivitySerializer(PaginateSerializer):
    results = ActivitySerializer(many=True)
