import json
import logging
from datetime import date
from typing import Optional

from django.db.models import Count, Q, Sum
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers

from src.accounts.serializers import UserSlimSerializer
from src.activity.models import ActivitySubscription, TokenHistory
from src.activity.serializers import ActivitySerializer
from src.games.models import GameCompany
from src.networks.serializers import NetworkSerializer
from src.promotion.serializers import (
    Promotion,
    PromotionSerializer,
    PromotionSlimSerializer,
)
from src.rates.api import calculate_amount
from src.rates.serializers import CurrencySerializer
from src.settings import config
from src.store.models import (
    Bid,
    Category,
    Collection,
    Ownership,
    Status,
    Tags,
    Token,
    TransactionTracker,
)
from src.support.models import Config
from src.utilities import PaginateSerializer, RedisClient


class PropertySerializer(serializers.Serializer):
    trait_type = serializers.CharField()
    trait_value = serializers.CharField()
    rarity = serializers.CharField()


class CollectionPropertySerializer(serializers.Serializer):
    amount = serializers.IntegerField()
    rarity = serializers.CharField()


class CollectionLayerSerializer(serializers.DictField):
    amount = serializers.IntegerField()
    perks = serializers.CharField()


class GameCompanyListSerializer(serializers.ModelSerializer):
    """
    moved here to prebent circular imports
    """

    network = NetworkSerializer(read_only=True)

    class Meta:
        model = GameCompany
        fields = ("id", "name", "description", "avatar", "network")


class TagSerializer(serializers.ModelSerializer):
    image = serializers.CharField(source="ipfs_image")
    banner = serializers.CharField(source="ipfs_banner")

    class Meta:
        model = Tags
        fields = (
            "id",
            "name",
            "image",
            "banner",
            "description",
        )


class CategorySerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True)
    image = serializers.CharField(source="ipfs_image")
    banner = serializers.CharField(source="ipfs_banner")

    class Meta:
        model = Category
        fields = ("id", "name", "tags", "image", "banner", "description")


class OwnershipSerializer(serializers.ModelSerializer):
    url = serializers.CharField(source="owner.url")
    name = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    selling_quantity = serializers.SerializerMethodField()
    avatar = serializers.CharField(read_only=True, source="owner.avatar")
    currency = CurrencySerializer()
    address = serializers.CharField(source="owner.username")

    class Meta:
        model = Ownership
        read_only_fields = ("avatar",)
        fields = read_only_fields + (
            "url",
            "name",
            "quantity",
            "selling_quantity",
            "price",
            "currency",
            "address",
        )

    def get_name(self, obj):
        return obj.owner.get_name()

    def get_quantity(self, obj):
        tracker_amount = (
            TransactionTracker.objects.filter(ownership=obj)
            .aggregate(owner_amount=Sum("amount"))
            .get("owner_amount")
        )
        tracker_amount = tracker_amount or 0
        quantity = obj.quantity or 0
        return max(quantity - tracker_amount, 0)

    def get_selling_quantity(self, obj):
        tracker_amount = (
            TransactionTracker.objects.filter(ownership=obj)
            .aggregate(owner_amount=Sum("amount"))
            .get("owner_amount")
        ) or 0
        selling_quantity = obj.selling_quantity or 0
        return max(selling_quantity - tracker_amount, 0)


class BidSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(source="token.currency")
    user = UserSlimSerializer()

    class Meta:
        model = Bid
        fields = (
            "id",
            "quantity",
            "amount",
            "currency",
            "state",
            "user",
        )


class CollectionSlimSerializer(serializers.ModelSerializer):
    """Serializer with basic information about collection"""

    network = NetworkSerializer()

    class Meta:
        model = Collection
        fields = (
            "url",
            "description",
            "name",
            "avatar",
            "address",
            "is_default",
            "cover",
            "standard",
            "symbol",
            "site",
            "discord",
            "twitter",
            "instagram",
            "medium",
            "telegram",
            "creator_royalty",
            "is_imported",
            "is_verified",
            "network",
            "block_difference",
        )


class CollectionFloorSerializer(CollectionSlimSerializer):
    floor_price = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()

    class Meta(CollectionSlimSerializer.Meta):
        fields = CollectionSlimSerializer.Meta.fields + (
            "currency",
            "floor_price",
        )

    def get_floor_price(self, obj) -> int:
        token = self.get_token_with_min_price(obj)
        if token:
            return token.price
        return 0

    @swagger_serializer_method(serializer_or_field=CurrencySerializer())
    def get_currency(self, obj):
        token = self.get_token_with_min_price(obj)
        if token:
            return CurrencySerializer(token.currency).data

    def get_token_with_min_price(self, obj) -> Optional["Token"]:
        tokens = list(obj.tokens.committed())
        owners = Ownership.objects.filter(token__in=tokens).filter(
            selling=True, currency__isnull=False
        )
        min_price_owner = None
        owners = [owner for owner in owners if owner.price_or_minimal_bid_usd]
        if owners:
            min_price_owner = sorted(
                list(owners), key=lambda x: x.price_or_minimal_bid_usd
            )[0]
        if min_price_owner:
            token = min_price_owner.token
            return token


class CompositeCollectionSerializer(CollectionFloorSerializer):
    """
    SlimCollection with creator, likes count and
    images of last 6 committed tokens.
    """

    creator = UserSlimSerializer()
    tokens = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    volume_traded = serializers.SerializerMethodField()

    class Meta(CollectionFloorSerializer.Meta):
        fields = CollectionFloorSerializer.Meta.fields + (
            "creator",
            "tokens",
            "likes_count",
            "volume_traded",
        )

    def get_tokens(self, obj) -> list:
        tokens = obj.tokens.committed().order_by(config.SORT_STATUSES.recent)[:6]
        return [token.media for token in tokens]

    def get_likes_count(self, obj) -> int:
        return obj.tokens.committed().aggregate(likes_count=Count("likes"))

    def get_volume_traded(self, obj) -> float:
        return (
            TokenHistory.objects.filter(
                token__collection=obj,
                method="Buy",
            )
            .aggregate(usd_sum=Sum("USD_price"))
            .get("usd_sum")
        )


class TrendingCollectionSerializer(CollectionFloorSerializer):
    """SlimCollection with creator and views count."""

    creator = UserSlimSerializer()
    views = serializers.IntegerField()

    class Meta(CollectionFloorSerializer.Meta):
        fields = CollectionFloorSerializer.Meta.fields + (
            "creator",
            "views",
        )


class TokenSlimSerializer(serializers.ModelSerializer):
    is_selling = serializers.BooleanField()
    is_auc_selling = serializers.BooleanField()
    is_timed_auc_selling = serializers.BooleanField()
    usd_price = serializers.FloatField()
    has_digital_key = serializers.BooleanField()
    collection = CollectionSlimSerializer()
    network = NetworkSerializer(source="collection.network")
    creator = UserSlimSerializer()
    is_liked = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()
    sellers = serializers.SerializerMethodField()
    currency = CurrencySerializer()
    promotion_info = serializers.SerializerMethodField()
    on_promotion = serializers.SerializerMethodField()
    end_auction = serializers.SerializerMethodField()

    class Meta:
        model = Token
        fields = (
            "id",
            "is_selling",
            "is_auc_selling",
            "is_timed_auc_selling",
            "name",
            "media",
            "animation",
            "total_supply",
            "currency",
            "internal_id",
            "available",
            "standard",
            "collection",
            "creator",
            "is_liked",
            "like_count",
            "description",
            "created_at",
            "format",
            "network",
            "external_link",
            "has_digital_key",
            "sellers",
            "price",
            "usd_price",
            "promotion_info",
            "on_promotion",
            "minimal_bid",
            "end_auction",
        )

    def get_on_promotion(self, obj) -> bool:
        return obj.promotions.filter(
            status=Promotion.PromotionStatus.IN_PROGRESS
        ).exists()

    @swagger_serializer_method(serializer_or_field=PromotionSerializer())
    def get_promotion_info(self, obj):
        user = self.context.get("user")
        show_promotion = self.context.get("show_promotion")
        promotions = obj.promotions.all()
        if show_promotion and user and not user.is_anonymous:
            user_promotions = promotions.filter(owner__owner=user)
            promotion = user_promotions.last()
            if promotion:
                return PromotionSerializer(promotion).data
        else:
            promotion = promotions.last()
            if promotion:
                return PromotionSlimSerializer(promotion).data

    @swagger_serializer_method(serializer_or_field=OwnershipSerializer(many=True))
    def get_sellers(self, obj) -> list:
        """List of ownerships which sell token."""
        sellers = obj.ownerships.filter(
            selling=True,
        ).order_by("price")
        return OwnershipSerializer(sellers, many=True).data

    def get_available(self, obj) -> int:
        """Count of available for buy tokens."""
        sellers = self.get_sellers(obj)
        amounts = [s.get("selling_quantity", 0) for s in sellers]
        return sum(amounts)

    def get_like_count(self, obj) -> int:
        return obj.likes.count()

    def get_is_liked(self, obj) -> bool:
        """Is currenct user like this token."""
        user = self.context.get("user")
        if user and not user.is_anonymous:
            return obj.likes.filter(user=user).exists()
        return False

    def get_end_auction(self, obj):
        if obj.is_single:
            return obj.ownerships.first().end_auction

    # def get_currency(self, obj) -> 'CurrencySerializer':
    #    return CurrencySerializer(obj.currency).data


class TokenSerializer(TokenSlimSerializer):
    category = CategorySerializer()
    owners = serializers.SerializerMethodField()
    bids = serializers.SerializerMethodField()
    digital_key = serializers.SerializerMethodField()
    highest_bid = BidSerializer(source="get_highest_bid")
    network = NetworkSerializer(source="collection.network")

    class Meta(TokenSlimSerializer.Meta):
        fields = TokenSlimSerializer.Meta.fields + (
            "owners",
            "digital_key",
            "bids",
            "category",
            "highest_bid",
        )

    @swagger_serializer_method(serializer_or_field=BidSerializer(many=True))
    def get_bids(self, obj):
        return BidSerializer(obj.bids.filter(state=Status.COMMITTED), many=True).data

    @swagger_serializer_method(serializer_or_field=OwnershipSerializer(many=True))
    def get_owners(self, obj):
        # is request sender is owner, make him first in queryset (on frontend demand)
        user = self.context.get("user")
        ownerships = sorted(
            obj.ownerships.all(), key=lambda x: x.owner == user, reverse=True
        )
        return OwnershipSerializer(ownerships, many=True).data

    def get_digital_key(self, obj) -> Optional[str]:
        """Return digital key if currenct user is token owner."""
        user = self.context.get("user")
        if user in obj.owners.all():
            return obj.digital_key
        return None

    # def get_owners(self, obj):
    #     return OwnershipSerializer(obj.ownerships.all(), many=True).data


class CollectionSerializer(CollectionFloorSerializer):
    """Full collection serializer"""

    creator = UserSlimSerializer()
    tokens_count = serializers.SerializerMethodField()
    properties = serializers.SerializerMethodField()
    floor_price = serializers.SerializerMethodField()
    owners_count = serializers.SerializerMethodField()
    volume_traded = serializers.SerializerMethodField()
    volume_traded_crypto = serializers.SerializerMethodField()
    subcategory_name = serializers.SerializerMethodField()

    class Meta(CollectionFloorSerializer.Meta):
        fields = CollectionFloorSerializer.Meta.fields + (
            "creator",
            "tokens_count",
            "properties",
            "floor_price",
            "owners_count",
            "volume_traded",
            "volume_traded_crypto",
            "subcategory_name",
        )

    def get_subcategory_name(self, obj) -> str:
        if obj.game_subcategory:
            return obj.game_subcategory.name

    def get_tokens_count(self, obj) -> int:
        return obj.tokens.committed().count()

    def get_owners_count(self, obj) -> int:
        """Return owners of collection."""
        return (
            obj.tokens.committed()
            .aggregate(count=Count("ownerships__owner", distinct=True))
            .get("count")
        )

    def get_volume_traded(self, obj):
        """Return sum of token prices in usd."""
        return (
            TokenHistory.objects.filter(
                token__collection=obj,
                method="Buy",
            )
            .aggregate(usd_sum=Sum("USD_price"))
            .get("usd_sum")
        )

    def get_volume_traded_crypto(self, obj) -> float:
        usd_sum = (
            TokenHistory.objects.filter(
                token__collection=obj,
                method="Buy",
            )
            .aggregate(usd_sum=Sum("USD_price"))
            .get("usd_sum")
        ) or 0
        amount = calculate_amount(
            usd_sum, from_currency="USD", to_currency=obj.network.native_symbol
        )
        return float("{0:.2f}".format(amount))

    @swagger_serializer_method(
        serializer_or_field=serializers.DictField(
            child=CollectionLayerSerializer(child=CollectionPropertySerializer())
        )
    )
    def get_properties(self, obj) -> dict:
        connection = RedisClient().connection
        cached_data = connection.get(f"perks_{obj.id}")
        if cached_data:
            data = json.loads(cached_data)
            return data
        return {}


class TokenFullSerializer(TokenSerializer):
    history = serializers.SerializerMethodField()
    views_count = serializers.SerializerMethodField()
    start_auction = serializers.SerializerMethodField()
    game = GameCompanyListSerializer()
    properties = PropertySerializer(many=True)

    class Meta(TokenSerializer.Meta):
        fields = TokenSerializer.Meta.fields + (
            "history",
            "views_count",
            "properties",
            "start_auction",
            "game",
        )

    @swagger_serializer_method(serializer_or_field=ActivitySerializer(many=True))
    def get_history(self, obj):
        # get all distinct token activities with doubling queryset due to problems in SQL with DISTINCT ON and ORDER
        activities = ActivitySubscription.objects.filter(
            Q(token_history__token=obj) | Q(bids_history__token=obj),
            source__isnull=True,
        ).distinct("token_history", "bids_history")
        activities = activities.values_list("id", flat=True)
        activities = ActivitySubscription.objects.filter(id__in=activities).order_by(
            "-date"
        )
        return ActivitySerializer(activities, many=True).data

    def get_start_auction(self, obj):
        if obj.is_single:
            return obj.ownerships.first().start_auction

    def get_views_count(self, obj):
        return obj.views.count()


class TokenFastSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Token
        fields = ("id", "name", "media")


class CollectionFastSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = ("id", "name", "cover", "avatar")


class PaginateCompositeCollectionSerializer(PaginateSerializer):
    results = CompositeCollectionSerializer(many=True)


class PaginateTokenSerializer(PaginateSerializer):
    results = TokenSerializer(many=True)


class PaginateTokenSlimSerializer(PaginateSerializer):
    results = TokenSlimSerializer(many=True)


class PaginateTokenFullSerializer(PaginateSerializer):
    results = TokenFullSerializer(many=True)


class TokenCreatingSerializer(serializers.Serializer):
    initial_tx = serializers.JSONField()
    token = TokenFullSerializer()


class CollectionCreatingSerializer(serializers.Serializer):
    initial_tx = serializers.JSONField()
    token = CollectionSlimSerializer()


class TopCollectionsSerializer(CollectionSlimSerializer):
    total_items = serializers.SerializerMethodField()
    total_owners = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    volume_traded = serializers.SerializerMethodField()

    class Meta(CollectionSlimSerializer.Meta):
        fields = CollectionSlimSerializer.Meta.fields + (
            "amount",
            "total_items",
            "total_owners",
            "volume_traded",
        )

    def get_amount(self, obj):
        start_date = self.context.get("start_date")
        end_date = self.context.get("end_date")
        return obj.stats.filter(date__gte=start_date, date__lte=end_date).aggregate(
            sum_amount=Sum("amount")
        )["sum_amount"]

    def get_total_items(self, obj):
        return obj.tokens.committed().count()

    def get_total_owners(self, obj):
        return (
            obj.tokens.committed()
            .values("owners")
            .distinct()
            .aggregate(Count("owners"))
            .get("owner__count")
        )

    def get_volume_traded(self, obj) -> float:
        start_date, period = Config.get_top_collections_period()
        end_date = date.today()
        return obj.stats.filter(date__gte=start_date, date__lte=end_date).aggregate(
            sum_amount=Sum("amount")
        )["sum_amount"]


class CollectionPatchSerializer(serializers.ModelSerializer):
    """
    Serialiser for AdvUser model patching
    """

    class Meta:
        model = Collection
        fields = (
            "description",
            "site",
            "medium",
            "twitter",
            "instagram",
            "telegram",
            "discord",
            "creator_royalty",
            "is_imported",
        )

    def update(self, instance, validated_data):
        logging.info("started collection patch")
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class PaginateTopCollectionsSerializer(PaginateSerializer):
    results = TopCollectionsSerializer(many=True)


class FastSearchSerializer(serializers.Serializer):
    users = UserSlimSerializer(many=True)
    tokens = TokenFastSearchSerializer(many=True)
    collections = CollectionFastSearchSerializer(many=True)
