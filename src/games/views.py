from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Exists, OuterRef
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from src.accounts.exceptions import UserNotFound
from src.accounts.models import AdvUser
from src.games.exceptions import (
    GameCategoryNotFound,
    GameCompanyExists,
    GameCompanyNotFound,
    GameSubCategoryNotFound,
    NameIsOccupied,
)
from src.games.models import GameCategory, GameCompany, GameSubCategory
from src.games.serializers import (
    GameCategoryCreateSerializer,
    GameCategoryPatchSerializer,
    GameCategorySerializer,
    GameCollectionCreateSerializer,
    GameCompanyCreateSerializer,
    GameCompanySerializer,
    GameSubCategoryCreateSerializer,
    GameSubCategoryPatchSerializer,
    GameSubCategorySerializer,
)
from src.games.utils import base64_to_ipfs
from src.networks.exceptions import NetworkNotFound
from src.networks.models import Network
from src.store.exceptions import CollectionNotFound, Forbidden
from src.store.models import Collection, Status
from src.store.serializers import GameCompanyListSerializer
from src.store.services.ipfs import send_to_ipfs
from src.store.views import error_response
from src.utilities import PaginateMixin


class CreateView(APIView):
    """
    View for list a game.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="list new game",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING),
                "email": openapi.Schema(type=openapi.FORMAT_EMAIL),
                "network": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="comma separated list of categories ids",
                ),
                "website": openapi.Schema(type=openapi.TYPE_STRING),
                "twitter": openapi.Schema(type=openapi.TYPE_STRING),
                "telegram": openapi.Schema(type=openapi.TYPE_STRING),
                "instagram": openapi.Schema(type=openapi.TYPE_STRING),
                "medium": openapi.Schema(type=openapi.TYPE_STRING),
                "discord": openapi.Schema(type=openapi.TYPE_STRING),
                "description": openapi.Schema(type=openapi.TYPE_STRING),
                "whitepaper_link": openapi.Schema(type=openapi.TYPE_STRING),
                "categories": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "name": openapi.Schema(type=openapi.TYPE_STRING),
                            "subcategories": openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Items(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        "name": openapi.Schema(
                                            type=openapi.TYPE_STRING
                                        ),
                                        "addresses": openapi.Schema(
                                            type=openapi.TYPE_ARRAY,
                                            items=openapi.Items(
                                                type=openapi.TYPE_OBJECT,
                                                properties={
                                                    "address": openapi.Schema(
                                                        type=openapi.TYPE_STRING
                                                    ),
                                                },
                                            ),
                                        ),
                                    },
                                ),
                            ),
                        },
                    ),
                ),
            },
            required=["name", "contact_email", "network"],
        ),
        responses={200: "created", 404: error_response},
    )
    @transaction.atomic
    def post(self, request):
        user = request.user
        network_name = request.data.get("network")
        network = Network.objects.filter(name=network_name).first()
        if not network:
            raise NetworkNotFound
        matching_game_company = GameCompany.objects.filter(
            name__iexact=request.data.get("name"),
            network=network,
        ).exclude(is_approved=False)
        if matching_game_company:
            raise GameCompanyExists
        serializer = GameCompanyCreateSerializer(
            data=request.data, context={"network": network.id, "user": user.id}
        )
        serializer.is_valid()
        if serializer.errors:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response("created", status=status.HTTP_200_OK)


class CreateGameCategoryView(APIView):
    """
    View for list a game.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="create new category",
        request_body=openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(
                type=openapi.TYPE_OBJECT,
                properties={
                    "name": openapi.Schema(type=openapi.TYPE_STRING),
                    "subcategories": openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Items(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "name": openapi.Schema(type=openapi.TYPE_STRING),
                                "addresses": openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Items(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "address": openapi.Schema(
                                                type=openapi.TYPE_STRING
                                            ),
                                        },
                                    ),
                                ),
                            },
                        ),
                    ),
                },
            ),
            required=["name", "subcategories"],
        ),
        responses={200: "created", 404: error_response},
    )
    @transaction.atomic
    def post(self, request, game_name, network):
        game_company = GameCompany.objects.filter(
            name__iexact=game_name, network__name__iexact=network, is_approved=True
        ).first()
        if not game_company:
            raise GameCompanyNotFound

        if request.user != game_company.user:
            raise Forbidden

        matching_game_category = GameCategory.objects.filter(
            name__iexact=request.data.get("name"), game=game_company
        ).exclude(is_approved=False)

        if matching_game_category:
            raise NameIsOccupied

        serializer_context = {
            "game": game_company.id,
            "network": game_company.network.id,
            "user": request.user.id,
        }
        serializer = GameCategoryCreateSerializer(
            data=request.data, context=serializer_context, many=True
        )
        serializer.is_valid()
        if serializer.errors:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        return Response("created", status=status.HTTP_200_OK)


class CreateGameSubCategoryView(APIView):
    """
    View for list a game.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="create new category",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING),
                "addresses": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "address": openapi.Schema(type=openapi.TYPE_STRING),
                        },
                    ),
                ),
            },
            required=["name", "addresses"],
        ),
        responses={200: "created", 404: error_response},
    )
    @transaction.atomic
    def post(self, request, game_name, network, category_name):
        game_category = GameCategory.objects.filter(
            game__name__iexact=game_name,
            game__is_approved=True,
            name__iexact=category_name,
            game__network__name__iexact=network,
        ).first()
        if not game_category:
            raise GameCategoryNotFound

        if request.user != game_category.game.user:
            raise NameIsOccupied

        matching_game_subcategory = (
            GameSubCategory.objects.filter(
                name__iexact=request.data.get("name"), category=game_category
            )
            .exclude(is_approved=False)
            .exclude(id=game_category.id)
        )

        if matching_game_subcategory:
            raise Forbidden

        serializer_context = {
            "category": game_category.id,
            "network": game_category.game.network.id,
            "user": request.user.id,
        }
        serializer = GameSubCategoryCreateSerializer(
            data=request.data, context=serializer_context
        )
        serializer.is_valid()
        if serializer.errors:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        return Response("created", status=status.HTTP_200_OK)


class AddCollectionInSubCategoryView(APIView):
    """
    View for list a game.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="add collections to existing subcategory",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "addresses": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "address": openapi.Schema(type=openapi.TYPE_STRING),
                        },
                    ),
                ),
            },
        ),
        responses={200: "created", 404: error_response},
    )
    @transaction.atomic
    def post(self, request, game_name, network, category_name, subcategory_name):
        game_subcategory = GameSubCategory.objects.filter(
            category__game__name__iexact=game_name,
            category__name__iexact=category_name,
            category__game__is_approved=True,
            name__iexact=subcategory_name,
            category__game__network__name__iexact=network,
        ).first()
        if not game_subcategory:
            raise GameSubCategoryNotFound

        serializer_context = {
            "subcategory": game_subcategory.id,
            "network": game_subcategory.category.game.network.id,
            "user": request.user.id,
        }
        serializer = GameCollectionCreateSerializer(
            data=request.data, context=serializer_context
        )
        serializer.is_valid()
        if serializer.errors:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        return Response("created", status=status.HTTP_200_OK)


class GetGameView(APIView):
    """
    View for get game info
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_description="get game info",
        responses={200: GameCompanySerializer, 400: GameCompanyNotFound.default_detail},
    )
    def get(self, _, game_name, network):
        game_company = GameCompany.objects.filter(
            name__iexact=game_name, network__name__iexact=network, is_approved=True
        ).first()
        if not game_company:
            raise GameCompanyNotFound
        response_data = GameCompanySerializer(game_company).data
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="patch game company info",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING),
                "email": openapi.Schema(type=openapi.TYPE_STRING),
                "whitepaper_link": openapi.Schema(type=openapi.TYPE_STRING),
                "background_coloe": openapi.Schema(type=openapi.TYPE_STRING),
                "description": openapi.Schema(type=openapi.TYPE_STRING),
                "website": openapi.Schema(type=openapi.TYPE_STRING),
                "twitter": openapi.Schema(type=openapi.TYPE_STRING),
                "instagram": openapi.Schema(type=openapi.TYPE_STRING),
                "telegram": openapi.Schema(type=openapi.TYPE_STRING),
                "discord": openapi.Schema(type=openapi.TYPE_STRING),
                "medium": openapi.Schema(type=openapi.TYPE_STRING),
                "facebook": openapi.Schema(type=openapi.TYPE_STRING),
                "avatar": openapi.Schema(type=openapi.FORMAT_BINARY),
                "remove_avatar": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "banner": openapi.Schema(type=openapi.FORMAT_BINARY),
                "remove_banner": openapi.Schema(type=openapi.TYPE_BOOLEAN),
            },
        ),
        responses={
            200: GameCompanySerializer,
            400: GameCompanyNotFound.default_detail,
            403: Forbidden.default_detail,
        },
    )
    def patch(self, request, game_name, network):
        game_company = GameCompany.objects.filter(
            name__iexact=game_name, network__name__iexact=network, is_approved=True
        ).first()
        if not game_company:
            raise GameCompanyNotFound

        if request.user != game_company.user:
            raise Forbidden

        serializer = GameCompanySerializer(
            game_company, data=request.data, partial=True
        )

        if serializer.is_valid():
            serializer.save()

        if serializer.errors:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        game_company.refresh_from_db()
        avatar = request.FILES.get("avatar")

        if request.data.get("remove_avatar"):
            game_company.avatar_ipfs = None
        if avatar:
            ipfs = send_to_ipfs(avatar)
            game_company.avatar_ipfs = ipfs

        banner = request.FILES.get("banner")

        if request.data.get("remove_banner"):
            game_company.banner_ipfs = None
        if banner:
            banner_ipfs = send_to_ipfs(banner)
            game_company.banner_ipfs = banner_ipfs

        game_company.save()

        response = GameCompanySerializer(game_company).data
        return Response(response, status=status.HTTP_200_OK)


class GameListView(APIView, PaginateMixin):
    @swagger_auto_schema(
        operation_description="list of games",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("text", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("order_by", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "items_per_page", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
        ],
        responses={
            200: GameCompanyListSerializer(many=True),
        },
    )
    def get(self, request):
        network = request.query_params.get("network")
        text = request.query_params.get("text")
        order_by = request.query_params.get("order_by")
        games = GameCompany.objects.filter(
            is_approved=True,
        )
        if network:
            games = games.filter(network__name=network)
        if text:
            games = games.filter(name__icontains=text)
        if order_by:
            games = games.order_by(order_by)
        return Response(
            self.paginate(request, games, GameCompanyListSerializer),
            status=status.HTTP_200_OK,
        )


class UserGameListView(APIView, PaginateMixin):
    @swagger_auto_schema(
        operation_description="list of user's games",
        manual_parameters=[
            openapi.Parameter(
                "user_id", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True
            ),
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "items_per_page", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
        ],
        responses={
            200: GameCompanySerializer(many=True),
        },
    )
    def get(self, request):
        user_id = request.query_params.get("user_id")
        network_name = request.query_params.get("network")
        try:
            user = AdvUser.objects.get_by_custom_url(user_id)
        except ObjectDoesNotExist:
            raise UserNotFound
        games = GameCompany.objects.filter(
            ~Exists(
                Collection.objects.filter(
                    game_subcategory__category__game__id=OuterRef("id"),
                    status=Status.IMPORTING,
                )
            ),
            is_approved=True,
            user=user,
        )
        if network_name:
            try:
                network = Network.objects.get(name__iexact=network_name)
            except ObjectDoesNotExist:
                raise NetworkNotFound
            games = games.filter(network=network)

        return Response(
            self.paginate(request, games, GameCompanySerializer),
            status=status.HTTP_200_OK,
        )


class GetGameCategoryView(APIView):
    """
    View for get game category info
    """

    # permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_description="get game category info",
        responses={
            200: GameCategorySerializer,
            401: GameCategoryNotFound.default_detail,
        },
    )
    def get(self, _, game_name, network, category_name):
        game_category = GameCategory.objects.filter(
            game__name__iexact=game_name,
            game__is_approved=True,
            name__iexact=category_name,
            game__network__name__iexact=network,
        ).first()
        if not game_category:
            raise GameCategoryNotFound

        response_data = GameCategorySerializer(game_category).data
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="patch game category info",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING),
                "avatar": openapi.Schema(type=openapi.FORMAT_BINARY),
                "remove_avatar": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "subcategories": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "id": openapi.Schema(type=openapi.TYPE_NUMBER),
                            "name": openapi.Schema(type=openapi.TYPE_STRING),
                            "avatar": openapi.Schema(type=openapi.FORMAT_BINARY),
                            "remove_avatar": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        },
                        required=["id"],
                    ),
                ),
            },
        ),
        responses={
            200: GameCategorySerializer,
            400: GameCategoryNotFound.default_detail,
            403: Forbidden.default_detail,
        },
    )
    @transaction.atomic()
    def patch(self, request, game_name, network, category_name):
        game_category = GameCategory.objects.filter(
            game__name__iexact=game_name,
            game__is_approved=True,
            name__iexact=category_name,
            game__network__name__iexact=network,
        ).first()
        if not game_category:
            raise GameCategoryNotFound

        if request.user != game_category.game.user:
            raise Forbidden

        matching_game_category = (
            GameCategory.objects.filter(
                name__iexact=request.data.get("name"), game=game_category.game
            )
            .exclude(is_approved=False)
            .exclude(id=game_category.id)
        )

        if matching_game_category:
            raise NameIsOccupied

        request_data = request.data.copy()
        if request_data.get("avatar"):
            request_data["avatar_ipfs"] = base64_to_ipfs(request_data["avatar"])
        for index, subcategory in enumerate(request_data.get("subcategories", [])):
            if subcategory.get("avatar"):
                request_data["subcategories"][index]["avatar_ipfs"] = base64_to_ipfs(
                    subcategory["avatar"]
                )

        serializer = GameCategoryPatchSerializer(
            game_category, data=request_data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
        if serializer.errors:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        for subcategory in request_data.get("subcategories", []):
            game_subcategory = game_category.subcategories.filter(
                id=subcategory["id"]
            ).first()
            serializer = GameSubCategoryPatchSerializer(
                game_subcategory, data=subcategory, partial=True
            )
            if serializer.is_valid():
                serializer.save()
            if serializer.errors:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            if subcategory.get("remove_avatar"):
                game_subcategory.avatar_ipfs = None
                game_subcategory.save(update_fields=("avatar_ipfs",))

        if request.data.get("remove_avatar"):
            game_category.avatar_ipfs = None
            game_category.save(update_fields=("avatar_ipfs",))

        response = GameCategorySerializer(game_category).data
        return Response(response, status=status.HTTP_200_OK)


class GetGameSubCategoryView(APIView):
    """
    View for get game info
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_description="get game subcategory info",
        responses={
            200: GameSubCategorySerializer,
            401: GameSubCategoryNotFound.default_detail,
        },
    )
    def get(self, _, game_name, network, category_name, subcategory_name):
        game_subcategory = GameSubCategory.objects.filter(
            category__game__name__iexact=game_name,
            category__name__iexact=category_name,
            category__game__is_approved=True,
            name__iexact=subcategory_name,
            category__game__network__name__iexact=network,
        ).first()
        if not game_subcategory:
            raise GameSubCategoryNotFound

        response_data = GameSubCategorySerializer(game_subcategory).data
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="patch game company info",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING),
                "avatar": openapi.Schema(type=openapi.FORMAT_BINARY),
                "remove_avatar": openapi.Schema(type=openapi.TYPE_BOOLEAN),
            },
        ),
        responses={
            200: GameSubCategorySerializer,
            400: GameSubCategoryNotFound.default_detail,
            403: Forbidden.default_detail,
        },
    )
    def patch(self, request, game_name, network, category_name, subcategory_name):
        game_subcategory = GameSubCategory.objects.filter(
            category__game__name__iexact=game_name,
            category__name__iexact=category_name,
            category__game__is_approved=True,
            name__iexact=subcategory_name,
            category__game__network__name__iexact=network,
        ).first()
        if not game_subcategory:
            raise GameSubCategoryNotFound

        if request.user != game_subcategory.category.game.user:
            raise Forbidden

        matching_game_subcategory = (
            GameSubCategory.objects.filter(
                name__iexact=request.data.get("name"), category=game_subcategory.game
            )
            .exclude(is_approved=False)
            .exclude(id=game_subcategory.id)
        )
        if matching_game_subcategory:
            raise NameIsOccupied

        if "name" in request.data.keys():

            serializer = GameSubCategorySerializer(
                game_subcategory, data=request.data, partial=True
            )

            if serializer.is_valid():
                serializer.save()

            if serializer.errors:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            game_subcategory.refresh_from_db()

        avatar = request.FILES.get("avatar")

        if request.data.get("remove_avatar"):
            game_subcategory.avatar_ipfs = None
        if avatar:
            avatar_ipfs = send_to_ipfs(avatar)
            game_subcategory.avatar_ipfs = avatar_ipfs

        game_subcategory.save()

        response = GameSubCategorySerializer(game_subcategory).data
        return Response(response, status=status.HTTP_200_OK)


class DeleteCategoryView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="delete game category",
        responses={
            200: "deleted",
            403: Forbidden.default_detail,
            404: GameCategoryNotFound.default_detail,
        },
    )
    def delete(self, request, category_id):
        category = GameCategory.objects.filter(id=category_id).first()
        if not category:
            raise GameCategoryNotFound
        if request.user != category.game.user:
            raise Forbidden
        category.delete()
        return Response("deleted", status=status.HTTP_200_OK)


class DeleteSubCategoryView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="delete game subcategory",
        responses={
            200: "deleted",
            403: Forbidden.default_detail,
            404: GameSubCategoryNotFound.default_detail,
        },
    )
    def delete(self, request, subcategory_id):
        subcategory = GameSubCategory.objects.filter(id=subcategory_id).first()
        if not subcategory:
            raise GameSubCategoryNotFound
        if request.user != subcategory.category.game.user:
            raise Forbidden
        subcategory.delete()
        return Response("deleted", status=status.HTTP_200_OK)


class DeleteCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="delete game collection",
        responses={
            200: "deleted",
            403: Forbidden.default_detail,
            404: CollectionNotFound.default_detail,
        },
    )
    def delete(self, request, collection_id):
        try:
            collection = Collection.objects.get_by_short_url(collection_id)
        except ObjectDoesNotExist:
            raise CollectionNotFound
        if not collection.game or request.user != collection.game.user:
            raise Forbidden
        collection.game_subcategory = None
        collection.save(update_fields=("game_subcategory",))
        return Response("deleted", status=status.HTTP_200_OK)
