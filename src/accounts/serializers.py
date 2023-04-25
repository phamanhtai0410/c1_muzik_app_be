import logging

from drf_yasg.utils import swagger_serializer_method
from rest_auth.registration.serializers import SocialLoginSerializer
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from src.accounts.models import AdvUser
from src.accounts.utils import valid_metamask_message
from src.settings import config
from src.store.models import Status, Token
from src.utilities import PaginateSerializer


class TokenSlimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Token
        ref_name = "AccountTokenSlim"
        fields = ("id", "media")


class PatchSerializer(serializers.ModelSerializer):
    """
    Serialiser for AdvUser model patching
    """

    class Meta:
        model = AdvUser
        fields = (
            "display_name",
            "custom_url",
            "bio",
            "twitter",
            "instagram",
            "facebook",
            "site",
            "cover_ipfs",
            "avatar_ipfs",
            "email",
        )

    def update(self, instance, validated_data):
        logging.info("started patch")
        url_field = config.USER_URL_FIELD
        if validated_data.get(url_field) and validated_data.get(url_field).isdigit():
            return {url_field: "can't contain only digits"}
        for attr, value in validated_data.items():
            if attr not in ("bio", "cover_ipfs", "avatar_ipfs") and value:
                my_filter = {attr: value}
                if attr == "display_name" and value == "":
                    pass
                elif AdvUser.objects.filter(**my_filter).exclude(id=instance.id):
                    return {attr: f"this {attr} is occupied"}
            setattr(instance, attr, value)
        instance.save()
        return instance


class MetamaskLoginSerializer(SocialLoginSerializer):
    address = serializers.CharField(required=False, allow_blank=True)
    signed_msg = serializers.CharField(required=False, allow_blank=True)

    access_token = None
    code = None

    def validate(self, attrs):
        address = attrs["address"]
        signature = attrs["signed_msg"]

        if valid_metamask_message(address, signature):
            metamask_user = AdvUser.objects.filter(username__iexact=address).first()

            if metamask_user is None:
                self.user = AdvUser.objects.create(username=address)
            else:
                self.user = metamask_user

            attrs["user"] = self.user

            if not self.user.is_active:
                raise PermissionDenied(1035)

        else:
            raise PermissionDenied(1034)

        return attrs


class CoverSerializer(serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()

    class Meta:
        model = AdvUser
        fields = (
            "url",
            "owner",
            "avatar",
            "cover_ipfs",
        )

    def get_owner(self, obj):
        return obj.get_name()


class UserSlimSerializer(serializers.ModelSerializer):
    address = serializers.ReadOnlyField(source="username")
    name = serializers.ReadOnlyField(source="get_name")

    class Meta:
        model = AdvUser
        fields = (
            "id",
            "url",
            "name",
            "address",
            "display_name",
            "custom_url",
            "created_at",
            "site",
            "is_verificated",
            "avatar",
            "bio",
            "twitter",
            "instagram",
            "facebook",
            "avatar",
            "email",
            "cover",
        )


class BaseAdvUserSerializer(UserSlimSerializer):
    created_tokens_count = serializers.SerializerMethodField()
    owned_tokens_count = serializers.SerializerMethodField()

    class Meta(UserSlimSerializer.Meta):
        fields = UserSlimSerializer.Meta.fields + (
            "created_tokens_count",
            "owned_tokens_count",
        )

    def get_created_tokens_count(self, obj) -> int:
        return obj.created_tokens.filter(status=Status.COMMITTED).count()

    def get_owned_tokens_count(self, obj) -> int:
        owned_tokens = Token.objects.filter(owners=obj).filter(status=Status.COMMITTED)
        network = self.context.get("network")
        if network:
            owned_tokens = owned_tokens.filter(
                collection__network__name__icontains=network
            )
        return owned_tokens.count()


class UserFollowSerializer(BaseAdvUserSerializer):
    followers_count = serializers.SerializerMethodField()
    tokens = serializers.SerializerMethodField()

    class Meta(BaseAdvUserSerializer.Meta):
        fields = BaseAdvUserSerializer.Meta.fields + (
            "followers_count",
            "tokens",
        )

    def get_followers_count(self, obj) -> int:
        return obj.following.filter(method="follow").count()

    @swagger_serializer_method(serializer_or_field=TokenSlimSerializer(many=True))
    def get_tokens(self, obj):
        tokens = obj.owned_tokens.committed()[:5]
        return TokenSlimSerializer(tokens, many=True).data


class UserSerializer(UserSlimSerializer):
    follows = serializers.SerializerMethodField()
    follows_count = serializers.SerializerMethodField()
    followers = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta(UserSlimSerializer.Meta):
        fields = UserSlimSerializer.Meta.fields + (
            "follows",
            "follows_count",
            "followers",
            "followers_count",
            "is_following",
        )

    @swagger_serializer_method(serializer_or_field=UserFollowSerializer(many=True))
    def get_follows(self, obj) -> list:
        followers = obj.followers.filter(method="follow")
        users = [follower.whom_follow for follower in followers]
        return UserFollowSerializer(users, many=True).data

    def get_follows_count(self, obj) -> int:
        return obj.followers.filter(method="follow").count()

    @swagger_serializer_method(serializer_or_field=UserFollowSerializer(many=True))
    def get_followers(self, obj):
        following = obj.following.filter(method="follow")
        users = [follower.user for follower in following]
        return UserFollowSerializer(users, many=True).data

    def get_followers_count(self, obj) -> int:
        return obj.following.filter(method="follow").count()

    def get_is_following(self, obj) -> bool:
        user = self.context.get("user")
        if user and not user.is_anonymous:
            return obj.following.filter(user=user, method="follow").exists()
        return False


class PaginateUserFollowSerializer(PaginateSerializer):
    results = UserFollowSerializer(many=True)
