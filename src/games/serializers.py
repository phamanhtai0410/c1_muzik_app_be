from django.db import IntegrityError
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers

from src.accounts.serializers import UserSlimSerializer
from src.games.exceptions import AlreadyListed
from src.games.signals import category_added, game_created, subcategory_added_updated
from src.networks.serializers import NetworkSerializer
from src.store.models import Collection, Status
from src.store.serializers import CollectionSlimSerializer
from src.utilities import AddressField

from .models import GameCategory, GameCompany, GameSubCategory


class GameSubCategorySerializer(serializers.ModelSerializer):
    collections = serializers.SerializerMethodField()
    owner = serializers.CharField(source="category.game.user.id")

    class Meta:
        model = GameSubCategory
        fields = ("id", "name", "avatar", "address_list", "collections", "owner")

    @swagger_serializer_method(serializer_or_field=CollectionSlimSerializer(many=True))
    def get_collections(self, obj):
        return CollectionSlimSerializer(obj.collections.committed(), many=True).data


class GameSubCategoryPatchSerializer(GameSubCategorySerializer):
    class Meta:
        model = GameSubCategory
        fields = ("name", "avatar_ipfs")


class GameCategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
    owner = serializers.CharField(source="game.user.id")

    @swagger_serializer_method(serializer_or_field=GameSubCategorySerializer(many=True))
    def get_subcategories(self, obj):
        return GameSubCategorySerializer(
            obj.subcategories.filter(is_approved=True), many=True
        ).data

    class Meta:
        model = GameCategory
        fields = ("id", "name", "avatar", "address_list", "subcategories", "owner")


class GameCategoryPatchSerializer(GameCategorySerializer):
    class Meta:
        model = GameCategory
        fields = ("name", "avatar_ipfs")


class GameCompanySerializer(serializers.ModelSerializer):
    user = UserSlimSerializer(read_only=True)
    network = NetworkSerializer(read_only=True)
    categories = GameCategorySerializer(many=True)
    avatar = serializers.CharField(read_only=True)
    banner = serializers.CharField(read_only=True)

    @swagger_serializer_method(serializer_or_field=GameCategorySerializer(many=True))
    def get_categories(self, obj):
        return GameCategorySerializer(
            obj.categories.filter(is_approved=True), many=True
        ).data

    class Meta:
        model = GameCompany
        fields = (
            "name",
            "email",
            "whitepaper_link",
            "background_color",
            "description",
            "website",
            "twitter",
            "instagram",
            "telegram",
            "discord",
            "medium",
            "facebook",
            "user",
            "network",
            "categories",
            "avatar",
            "banner",
        )

    def create(self, validated_data):
        context = self.context
        categories = validated_data.pop("categories")
        game_instance = self.Meta.model.objects.create(
            **validated_data,
            network_id=context.get("network"),
            user_id=context.get("user"),
        )
        for category in categories:
            create_category(context, game_instance, category)

        game_created.send(sender=self.Meta.model.__class__, instance=game_instance)
        return game_instance


class GameCollectionCreateSerializer(serializers.Serializer):
    addresses = serializers.ListField(child=serializers.DictField(child=AddressField()))

    def create(self, validated_data):
        context = self.context
        subcategory_instance = GameSubCategory.objects.get(
            id=context.get("subcategory")
        )
        addresses = validated_data.pop("addresses")
        subcategory_instance.category.game.validating_result = None
        subcategory_instance.category.game.save()
        create_collections(context, subcategory_instance, addresses)
        subcategory_added_updated.send(
            sender=GameSubCategory.__class__, instance=subcategory_instance
        )
        return subcategory_instance


class GameSubCategoryCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    addresses = serializers.ListField(child=serializers.DictField(child=AddressField()))

    def create(self, validated_data):
        context = self.context
        category = GameCategory.objects.get(id=context.get("category"))
        addresses = validated_data.pop("addresses")
        subcategory_instance = create_subcategory(
            context, category, addresses, {**validated_data}
        )
        category.game.validating_result = None
        category.game.save()
        subcategory_added_updated.send(
            sender=GameSubCategory.__class__, instance=subcategory_instance
        )
        return subcategory_instance


class GameCategoryCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    subcategories = GameSubCategoryCreateSerializer(many=True)

    def create(self, validated_data):
        context = self.context
        game_company = GameCompany.objects.get(id=context.get("game"))
        category_instance = create_category(context, game_company, {**validated_data})
        category_instance.game.validating_result = None
        category_instance.game.save()
        category_added.send(sender=GameCategory.__class__, instance=category_instance)
        return category_instance


class GameCompanyCreateSerializer(GameCompanySerializer):
    categories = GameCategoryCreateSerializer(many=True)


def create_collections(context, subcategory, addresses):
    for address in addresses:
        col = Collection.objects.filter(
            network_id=context.get("network"),
            address__iexact=address["address"],
            game_subcategory__isnull=True,
        ).first()
        if col:
            col.game_subcategory = subcategory
            col.save(update_fields=("game_subcategory",))
            return
        try:
            Collection.objects.create(
                network_id=context.get("network"),
                address=address["address"],
                creator_id=context.get("user"),
                creator_royalty=0,
                game_subcategory=subcategory,
                is_imported=True,
                status=Status.PENDING,
            )

        except IntegrityError:
            raise AlreadyListed(
                detail=f"Collection {address['address']} already listed"
            )


def create_subcategory(context, category, addresses, subcategory_data):
    subcategory_instance = GameSubCategory.objects.create(
        category=category, **subcategory_data
    )
    create_collections(context, subcategory_instance, addresses)
    return subcategory_instance


def create_category(context, game_company, input_data):
    subcategories = input_data.pop("subcategories")
    category_instance = GameCategory.objects.create(game=game_company, **input_data)
    for subcategory in subcategories:
        addresses = subcategory.pop("addresses")
        create_subcategory(context, category_instance, addresses, subcategory)

    return category_instance
