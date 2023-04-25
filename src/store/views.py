import logging
import random
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Subquery, Sum
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from src.accounts.exceptions import UserNotFound
from src.accounts.models import AdvUser
from src.accounts.serializers import PaginateUserFollowSerializer, UserSlimSerializer
from src.activity.models import BidsHistory, UserAction
from src.activity.serializers import (
    CollectionStatsSerializer,
    CollectionTradeDataSerializer,
)
from src.activity.services.top_collections import (
    get_collection_charts,
    get_collection_trade_data,
)
from src.games.exceptions import GameCompanyNotFound, GameSubCategoryNotFound
from src.games.models import GameCompany, GameSubCategory
from src.networks.exceptions import NetworkNotFound
from src.networks.models import Network
from src.promotion.models import Promotion
from src.rates.utils import get_currency_by_symbol
from src.responses import (
    error_response,
    max_price_response,
    success_response,
    tx_response,
)
from src.services.search import Search
from src.settings import config
from src.store.api import check_captcha
from src.store.exceptions import CollectionNotFound, Forbidden, TokenNotFound
from src.store.models import (
    Bid,
    Category,
    Collection,
    Ownership,
    Status,
    Tags,
    Token,
    TransactionTracker,
    ViewsTracker,
)
from src.store.serializers import (
    BidSerializer,
    CategorySerializer,
    CollectionCreatingSerializer,
    CollectionFastSearchSerializer,
    CollectionPatchSerializer,
    CollectionSerializer,
    CollectionSlimSerializer,
    FastSearchSerializer,
    PaginateCompositeCollectionSerializer,
    PaginateTokenSerializer,
    TagSerializer,
    TokenCreatingSerializer,
    TokenFastSearchSerializer,
    TokenFullSerializer,
    TokenSerializer,
    TokenSlimSerializer,
    TrendingCollectionSerializer,
)
from src.store.services.filetype_parser.parser import FiletypeParser
from src.store.services.ipfs import create_ipfs, send_to_ipfs
from src.store.utils import get_collection_by_short_url, get_committed_token
from src.store.validators import CollectionValidator
from src.support.models import EmailConfig
from src.utilities import PaginateMixin


class SearchView(APIView, PaginateMixin):
    """
    View for search items in shop.
    searching has simple 'contains' logic.
    """

    @swagger_auto_schema(
        operation_description="get search pattern. Due to limited functionality of drf_yasg schema, all 3 positive\
                               model outcome are mentioned with different code statuses, while they are all '200'",
        manual_parameters=[
            openapi.Parameter(
                "type",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Search by: items, users, collections, defaults to items",
            ),
            openapi.Parameter(
                "categories",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="comma separated list of categories ids",
            ),
            # openapi.Parameter("tags", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "collections",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="comma-separated list of collection urls (ids or short_urls)",
            ),
            openapi.Parameter(
                "related_collections",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="comma-separated list of collection urls (ids or short_urls) for related collections (same cubcategory",
            ),
            # openapi.Parameter(
            #    "is_verified", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN
            # ),
            openapi.Parameter(
                "min_price",
                openapi.IN_QUERY,
                type=openapi.TYPE_NUMBER,
                description="minimal price, should be used with currency for proper search",
            ),
            openapi.Parameter(
                "max_price",
                openapi.IN_QUERY,
                type=openapi.TYPE_NUMBER,
                description="maximal price, should be used with currency for proper search",
            ),
            openapi.Parameter(
                "order_by",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="For tokens: created_at, price, likes, views, sale, transfer, auction_end, last_sale. \n For users: created, followers, tokens_created, \n For collections: name",
            ),
            openapi.Parameter(
                "properties",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description='JSON in string format, where value is a list. e.g. {"Eyes":["Determined"]}',
            ),
            openapi.Parameter("on_sale", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter(
                "on_auc_sale", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN
            ),
            openapi.Parameter(
                "on_timed_auc_sale", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN
            ),
            openapi.Parameter(
                "on_any_sale", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "on_any_sale_by",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="url of seller",
            ),
            openapi.Parameter(
                "standard",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="ERC721 or ERC1155",
            ),
            openapi.Parameter(
                "currency",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="comma-separated list of currency symbols",
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
            openapi.Parameter(
                "items_per_page", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "network",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="comma-separated list of network names",
            ),
            openapi.Parameter(
                "creator",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="url of token creator",
            ),
            openapi.Parameter(
                "text",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="search pattern",
            ),
            openapi.Parameter(
                "owner",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="url of user",
            ),
            openapi.Parameter(
                "sold_by",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="url of user",
            ),
            openapi.Parameter(
                "bids_by",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="url of user",
            ),
            openapi.Parameter(
                "liked_by",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="url of user",
            ),
            openapi.Parameter(
                "category",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="category of collection",
            ),
            openapi.Parameter(
                "game",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description="id of the game",
            ),
        ],
        responses={
            200: PaginateTokenSerializer,
            201: PaginateCompositeCollectionSerializer,
            202: PaginateUserFollowSerializer,
            404: error_response,
        },
    )
    @method_decorator(cache_page(15))
    @method_decorator(
        vary_on_headers(
            "Authorization",
        )
    )
    def get(self, request):
        params = request.query_params.copy()
        sort = params.pop("type", ["items"])
        sort = sort[0]

        if sort not in config.SEARCH_TYPES.__dict__.keys():
            return Response(
                {"error": "type not found"}, status=status.HTTP_404_NOT_FOUND
            )

        sort_type = getattr(config.SEARCH_TYPES, sort)
        search = Search.get(sort_type)
        result = search.parse(
            current_user=request.user,
            **params,
        )
        paginated_result = self.paginate(request, result)
        paginated_result["results"] = search.serialize(paginated_result.get("results"))

        return Response(paginated_result, status=status.HTTP_200_OK)


class CreateView(APIView):
    """
    View for create token transaction.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="token_creation",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING),
                "total_supply": openapi.Schema(type=openapi.TYPE_NUMBER),
                "currency": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="symbol of currency if setting on sale",
                ),
                "description": openapi.Schema(type=openapi.TYPE_STRING),
                "price": openapi.Schema(
                    type=openapi.TYPE_NUMBER, description="token price without decimals"
                ),
                "minimal_bid": openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description="token minimal bid without decimals",
                ),
                "creator_royalty": openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description="royalty with up to 2 decimal digits",
                ),
                "selling_quantity": openapi.Schema(type=openapi.TYPE_NUMBER),
                "collection": openapi.Schema(
                    type=openapi.TYPE_NUMBER, description="id of collection"
                ),
                "details": openapi.Schema(
                    type=openapi.TYPE_OBJECT, description="json with key:value pairs"
                ),
                "selling": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "start_auction": openapi.Schema(type=openapi.FORMAT_DATETIME),
                "end_auction": openapi.Schema(type=openapi.FORMAT_DATETIME),
                "digital_key": openapi.Schema(type=openapi.TYPE_STRING),
                "media": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY
                ),
                "cover": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY
                ),
                "category": openapi.Schema(
                    type=openapi.TYPE_NUMBER, description="id of category"
                ),
            },
            required=["name", "collection", "media", "category"],
        ),
        responses={200: TokenCreatingSerializer, 404: error_response},
    )
    @transaction.atomic
    def post(self, request):
        collection = get_collection_by_short_url(request.data.get("collection"))
        # check if user can mint
        if request.user != collection.creator and not collection.is_default:
            raise Forbidden
        filetype_parser = FiletypeParser(request.FILES)
        media_type = filetype_parser.parse()
        total_supply = int(request.data.get("total_supply", 1))
        token = Token(collection=collection)
        validator = token.validator
        validator.is_name_unique_for_network(
            name=request.data.get("name"),
            network=collection.network,
        )
        validator.is_valid_data_for_sell(request.data.get("minimal_bid"))
        validator.is_valid_total_supply(int(total_supply))
        validator.is_cover_required(request.FILES, media_type)
        validator.is_valid_media(media_type)
        if request.data.get("selling"):
            validator.is_approved(request.user)

        errors = validator.errors
        if errors is not None:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        ipfs = create_ipfs(request)
        token.controller.save_in_db(request, ipfs, media_type)

        initial_tx = token.exchange.mint(
            ipfs=ipfs.get("general"),
            collection=collection,
            total_supply=total_supply,
            user=request.user,
        )

        response_data = {"initial_tx": initial_tx, "token": TokenSerializer(token).data}
        return Response(response_data, status=status.HTTP_200_OK)


class CreateCollectionView(APIView):
    """
    View for create collection transaction.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="collection_creation",
        manual_parameters=[
            openapi.Parameter(
                "network",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                required=True,
                description="name of network",
            ),
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "name": openapi.Schema(type=openapi.TYPE_STRING),
                "standard": openapi.Schema(
                    type=openapi.TYPE_STRING, description="ERC721 or ERC1155"
                ),
                "avatar": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY
                ),
                "game_subcategory_id": openapi.Schema(type=openapi.TYPE_NUMBER),
                "symbol": openapi.Schema(type=openapi.TYPE_STRING),
                "description": openapi.Schema(type=openapi.TYPE_STRING),
                "short_url": openapi.Schema(type=openapi.TYPE_STRING),
                "site": openapi.Schema(type=openapi.TYPE_STRING),
                "discord": openapi.Schema(type=openapi.TYPE_STRING),
                "twitter": openapi.Schema(type=openapi.TYPE_STRING),
                "instagram": openapi.Schema(type=openapi.TYPE_STRING),
                "medium": openapi.Schema(type=openapi.TYPE_STRING),
                "telegram": openapi.Schema(type=openapi.TYPE_STRING),
                "creator_royalty": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
            required=["name", "avatar", "symbol", "standard"],
        ),
        responses={200: CollectionCreatingSerializer, 400: error_response},
    )
    @transaction.atomic
    def post(self, request):
        name = request.data.get("name")
        symbol = request.data.get("symbol")
        short_url = request.data.get("short_url", "")
        game_subcategory_id = request.data.get("game_subcategory_id")
        standard = request.data.get("standard") or request.data.get(
            "standart"
        )  # reverse compatibility
        network_name = request.query_params.get("network", config.DEFAULT_NETWORK)
        network = Network.objects.filter(name=network_name).first()

        if not network:
            raise NetworkNotFound
        validator = CollectionValidator()
        validator.is_name_unique_for_network(name, network)
        validator.is_symbol_unique_for_network(symbol, network)
        validator.is_short_url_unique(short_url)
        validator.is_correct_standard(standard)

        game_subcategory = None
        if game_subcategory_id:
            game_subcategory = GameSubCategory.objects.filter(
                id=game_subcategory_id
            ).first()
            if not game_subcategory:
                raise GameSubCategoryNotFound
            validator.is_game_add_valid(game_subcategory, request.user)

        errors = validator.errors
        if errors is not None:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        collection = Collection()
        initial_tx = collection.exchange.create_contract(
            name,
            symbol,
            standard,
            request.user,
            network,
        )

        media = request.FILES.get("avatar")
        cover = request.FILES.get("cover")
        if media:
            ipfs = send_to_ipfs(media)
        else:
            ipfs = None
        if cover:
            cover = send_to_ipfs(cover)
        else:
            cover = None
        collection.save_in_db(request, ipfs, cover, game_subcategory)
        response_data = {
            "initial_tx": initial_tx,
            "collection": CollectionSlimSerializer(collection).data,
        }
        return Response(response_data, status=status.HTTP_200_OK)


class GetView(APIView):
    """
    View for get token info.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_description="get token info",
        responses={200: TokenFullSerializer, 404: error_response},
    )
    def get(self, request, token_id):
        token = get_committed_token(token_id)
        if request.user:
            ViewsTracker.objects.get_or_create(token=token, user_id=request.user.id)

        response_data = TokenFullSerializer(
            token, context={"user": request.user, "show_promotion": True}
        ).data
        return Response(response_data, status=status.HTTP_200_OK)


class TokenSetOnSaleView(APIView):
    """
    View for set token on sale.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Set token on sale.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "price": openapi.Schema(type=openapi.TYPE_NUMBER),
                "currency": openapi.Schema(
                    type=openapi.TYPE_STRING, description="symbol of currency"
                ),
                "amount": openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description="For 1155 token. Number of copies for sale.",
                ),
            },
            required=["price", "currency"],
        ),
        responses={
            200: TokenFullSerializer,
            400: error_response,
            404: TokenNotFound.default_detail,
        },
    )
    def post(self, request, token_id):
        user = request.user
        price = request.data.get("price")
        currency = request.data.get("currency")
        amount = request.data.get("amount")

        token = get_committed_token(token_id)

        errors = token.validator.is_committed().is_owner(user).has_bid().errors
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # if amount not set, pul all
        if not amount:
            ownership = token.ownerships.get(owner=user)

            if ownership.selling_quantity:
                amount = ownership.selling_quantity
            else:
                amount = ownership.quantity

        currency = get_currency_by_symbol(currency, token.collection.network)

        price = Decimal(str(price))

        # check price above minimal decimal
        price_with_decimals = int(price * currency.get_decimals)
        if price_with_decimals < 1:
            return Response(
                {"error": "Price below minimal decimal"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        errors = token.controller.change_sell_status(
            user=user,
            currency=currency.id,
            price=price,
            selling=True,
            amount=amount,
        )
        if errors:
            return Response({"error": errors}, status=status.HTTP_400_BAD_REQUEST)

        response_data = TokenFullSerializer(token, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)


class TokenSetOnAucSaleView(APIView):
    """
    View for set token on auction.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Set token on auction.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "minimal_bid": openapi.Schema(
                    type=openapi.TYPE_NUMBER, description="minimal_bid without decimals"
                ),
                "amount": openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description="For 1155 token. Number of copies for sale.",
                ),
                "currency": openapi.Schema(
                    type=openapi.TYPE_STRING, description="symbol of currency"
                ),
                "start_auction": openapi.Schema(type=openapi.FORMAT_DATETIME),
                "end_auction": openapi.Schema(type=openapi.FORMAT_DATETIME),
            },
            required=["minimal_bid", "currency"],
        ),
        responses={
            200: TokenFullSerializer,
            400: error_response,
            404: TokenNotFound.default_detail,
        },
    )
    def post(self, request, token_id):
        user = request.user
        minimal_bid = request.data.get("minimal_bid")
        currency = request.data.get("currency")
        amount = request.data.get("amount", 1)

        token = get_committed_token(token_id)
        if not token.is_single:
            return Response(
                {"error": "Token cannot be put on auction"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        errors = token.validator.is_committed().is_owner(user).has_bid().errors
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        currency = get_currency_by_symbol(currency, token.collection.network)
        if currency.address.lower() == token.native_address:
            return Response(
                {"error": "Invalid currency"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        minimal_bid = Decimal(str(minimal_bid))

        start_auction = request.data.get("start_auction")
        end_auction = request.data.get("end_auction")
        if end_auction and not start_auction:
            start_auction = timezone.now()

        # TODO: move to validator
        if end_auction and start_auction and start_auction > end_auction:
            return Response(
                {"error": "end_auction must be later than start_auction"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        errors = token.controller.change_sell_status(
            user=user,
            currency=currency.id,
            minimal_bid=minimal_bid,
            start_auction=start_auction,
            end_auction=end_auction,
            selling=True,
            amount=amount,
        )
        if errors:
            return Response({"error": errors}, status=status.HTTP_400_BAD_REQUEST)

        response_data = TokenFullSerializer(token, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)


class TokenRemoveFromSaleView(APIView):
    """
    View for remove token from sale.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Remove token from sale.",
        responses={
            200: TokenFullSerializer,
            400: error_response,
            404: TokenNotFound.default_detail,
        },
    )
    def post(self, request, token_id):
        user = request.user

        token = get_committed_token(token_id)

        validator = token.validator
        validator.is_committed()
        validator.is_owner(user)
        validator.is_removable_from_sale()
        errors = validator.errors
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        errors = token.controller.change_sell_status(user=user)
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        response_data = TokenFullSerializer(token, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)


class TokenBurnView(APIView):
    """
    View for burn token.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="token burn",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "amount": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        required=["amount"],
        responses={200: tx_response, 400: error_response},
    )
    def post(self, request, token_id):
        token = get_committed_token(token_id)
        amount = request.data.get("amount")
        errors = token.validator.is_committed().is_owner(request.user).has_bid().errors
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        # token.exchange.create_tx_tracker(request.user, amount)
        return Response(
            {"initial_tx": token.exchange.burn(request.user, amount)},
            status=status.HTTP_200_OK,
        )


class GetCollectionView(APIView):
    """
    View for get collection info in shop.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_description="get collection info",
        manual_parameters=[
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
        responses={200: CollectionSerializer, 400: CollectionNotFound.default_detail},
    )
    def get(self, _, param):
        collection = get_collection_by_short_url(param)
        response_data = CollectionSerializer(collection).data
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="patch collection info",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "description": openapi.Schema(type=openapi.TYPE_STRING),
                "site": openapi.Schema(type=openapi.TYPE_STRING),
                "telegram": openapi.Schema(type=openapi.TYPE_STRING),
                "twitter": openapi.Schema(type=openapi.TYPE_STRING),
                "medium": openapi.Schema(type=openapi.TYPE_STRING),
                "discord": openapi.Schema(type=openapi.TYPE_STRING),
                "instagram": openapi.Schema(type=openapi.TYPE_STRING),
                "avatar": openapi.Schema(type=openapi.FORMAT_BINARY),
                "remove_avatar": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                "creator_royalty": openapi.Schema(type=openapi.TYPE_BOOLEAN),
            },
        ),
        responses={
            200: CollectionSerializer,
            400: CollectionNotFound.default_detail,
            403: Forbidden.default_detail,
        },
    )
    def patch(self, request, param):
        collection = get_collection_by_short_url(param)
        if request.user != collection.creator:
            raise Forbidden
        serializer = CollectionPatchSerializer(
            collection, data=request.data, partial=True
        )

        if serializer.is_valid():
            serializer.save()
        if serializer.errors:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        collection.refresh_from_db()
        avatar = request.FILES.get("avatar")

        if request.data.get("remove_avatar"):
            collection.avatar_ipfs = None
            collection.save()
        if avatar:
            ipfs = send_to_ipfs(avatar)
            collection.avatar_ipfs = ipfs
            collection.save()
        response = CollectionSerializer(collection).data
        return Response(response, status=status.HTTP_200_OK)


class GetCollectionChartView(APIView):
    @swagger_auto_schema(
        operation_description="get collection price chart",
        manual_parameters=[
            openapi.Parameter("days", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
        responses={
            200: CollectionStatsSerializer(many=True),
            400: CollectionNotFound.default_detail,
        },
    )
    def get(self, request, param):
        collection = get_collection_by_short_url(param)
        days = request.query_params.get("days")
        collection_stats = get_collection_charts(collection, days)
        return Response(collection_stats, status=status.HTTP_200_OK)


class GetCollectionTradeDataView(APIView):
    @swagger_auto_schema(
        operation_description="get collection trade data",
        manual_parameters=[
            openapi.Parameter("days", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
        ],
        responses={
            200: CollectionTradeDataSerializer,
            400: CollectionNotFound.default_detail,
        },
    )
    def get(self, request, param):
        collection = get_collection_by_short_url(param)
        days = request.query_params.get("days")
        collection_data = get_collection_trade_data(collection, days)
        return Response(collection_data, status=status.HTTP_200_OK)


class TransferOwned(APIView):
    """
    View for tansfering token owned by user.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="transfer_owned",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "address": openapi.Schema(type=openapi.TYPE_STRING),
                "amount": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
            required=["address", "amount"],
        ),
        responses={
            200: tx_response,
            400: error_response,
            404: TokenNotFound.default_detail,
        },
    )
    def post(self, request, token_id):
        address = request.data.get("address")
        amount = request.data.get("amount")
        token = get_committed_token(token_id)

        errors = token.validator.is_committed().is_owner(request.user).has_bid().errors
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        initial_tx = token.exchange.transfer(request.user, address, amount)
        # token.exchange.create_tx_tracker(request.user, amount)
        return Response({"initial_tx": initial_tx}, status=status.HTTP_200_OK)


class BuyTokenView(APIView):
    """
    view to buy a token
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="buy_token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_NUMBER),
                "tokenAmount": openapi.Schema(type=openapi.TYPE_NUMBER),
                "sellerId": openapi.Schema(
                    type=openapi.TYPE_STRING, description="url of seller"
                ),
            },
            required=["id", "sellerId"],
        ),
        responses={
            200: tx_response,
            400: error_response,
            404: TokenNotFound.default_detail,
        },
    )
    def post(self, request):
        seller_id = request.data.get("sellerId")
        token_id = request.data.get("id")
        token_amount = request.data.get("tokenAmount", 0)

        if token_id is None:
            return Response(
                {"error": "invalid token_id"}, status=status.HTTP_400_BAD_REQUEST
            )
        if seller_id is None:
            return Response(
                {"error": "invalid seller_id"}, status=status.HTTP_400_BAD_REQUEST
            )

        token_id = int(token_id)
        token_amount = int(token_amount)
        tradable_token = get_committed_token(token_id)

        try:
            seller = AdvUser.objects.get_by_custom_url(seller_id)
        except AdvUser.DoesNotExist:
            raise UserNotFound

        errors = (
            tradable_token.validator.is_committed()
            .is_selling()
            .is_seller(seller)
            .is_valid_amount_for_buy(token_amount)
            .errors
        )
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        buy = tradable_token.exchange.buy(token_amount, request.user, seller)
        return Response({"initial_tx": buy}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    operation_description="List of categories",
    manual_parameters=[
        openapi.Parameter("name", openapi.IN_QUERY, type=openapi.TYPE_STRING),
    ],
    responses={200: CategorySerializer(many=True)},
)
@api_view(http_method_names=["GET"])
def get_categories(request):
    name = request.query_params.get("name")
    categories = Category.objects.all().order_by("id")
    if name:
        categories = categories.filter(name__icontains=name)
    return Response(
        CategorySerializer(
            categories,
            many=True,
        ).data,
        status=status.HTTP_200_OK,
    )


@swagger_auto_schema(
    method="get",
    operation_description="List of tags",
    responses={200: TagSerializer(many=True)},
)
@api_view(http_method_names=["GET"])
def get_tags(request):
    tags = Tags.objects.all().order_by("id")
    return Response(
        TagSerializer(
            tags,
            many=True,
        ).data,
        status=status.HTTP_200_OK,
    )


class MakeBid(APIView):
    """
    view for making bid on auction
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="make_bid",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "token_id": openapi.Schema(type=openapi.TYPE_NUMBER),
                "amount": openapi.Schema(type=openapi.TYPE_NUMBER),
                "currency": openapi.Schema(
                    type=openapi.TYPE_STRING, description="symbol of currency"
                ),
            },
            required=["token_id", "amount", "currency"],
        ),
        responses={
            200: "bid_created",
            400: error_response,
            404: TokenNotFound.default_detail,
        },
    )
    def post(self, request):
        request_data = request.data
        token_id = request_data.get("token_id")
        amount = Decimal(str(request_data.get("amount")))
        quantity = int(request_data.get("quantity", 1))
        currency = request_data.get("currency")
        token = get_committed_token(token_id)
        user = request.user

        network = token.collection.network
        currency = get_currency_by_symbol(currency, network)

        # returns OK if valid, or error message
        validator = token.validator
        validator.check_highest_bid(user=user, amount=amount)
        validator.check_validate_bid(user=user, amount=amount)
        errors = validator.errors

        if errors is not None:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # create new bid or update old one
        bid, created = Bid.objects.get_or_create(
            user=user, token=token, state=Status.COMMITTED
        )

        if not created and bid.amount >= amount:
            return Response(
                {"error": "you cannot lower your bid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # save data to bid
        bid.amount = amount
        bid.quantity = quantity
        bid.currency = currency
        bid.state = Status.COMMITTED
        bid.full_clean()
        bid.save()

        # create bid history
        BidsHistory.objects.create(
            token=bid.token,
            user=bid.user,
            price=bid.amount,
            date=bid.created_at,
            currency=currency,
        )

        return Response("bid created", status=status.HTTP_200_OK)


@api_view(http_method_names=["GET"])
@permission_classes([IsAuthenticated])
def get_bids(request, token_id):
    # validating token and user
    token = get_committed_token(token_id)
    if not token.is_auc_selling:
        return Response(
            {"error": "token is not set on auction"}, status=status.HTTP_400_BAD_REQUEST
        )
    if token.ownerships.first().owner != request.user:
        return Response(
            {"error": "you can get bids list only for owned tokens"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    bids = Bid.objects.filter(token=token)

    response_data = BidSerializer(bids, many=True).data
    return Response(response_data, status=status.HTTP_200_OK)


# TODO Is necessary?
class VerificateBetView(APIView):
    @swagger_auto_schema(
        operation_description="verificate bet",
        responses={200: BidSerializer, 404: TokenNotFound.default_detail},
    )
    def get(self, _, token_id):
        token = get_committed_token(token_id)
        bets = Bid.objects.filter(token=token).order_by("-amount")
        max_bet = bets.first()
        if not max_bet:
            return Response(
                {"invalid_bet": None, "valid_bet": None}, status=status.HTTP_200_OK
            )

        user = max_bet.user
        amount = max_bet.amount

        validator = token.validator
        validator.check_validate_bid(user=user, amount=amount)
        errors = validator.errors

        if errors is None:
            logging.info("all ok!")
            return Response(BidSerializer(max_bet).data, status=status.HTTP_200_OK)
        else:
            logging.info("not ok(")
            max_bet.delete()
            logging.info(bets)
            for bet in bets:
                user = bet.user
                amount = bet.amount
                validator = token.validator
                validator.check_validate_bid(user=user, amount=amount)
                errors = validator.errors
                if errors is None:
                    logging.info("again ok!")
                    return Response(
                        {
                            "invalid_bet": BidSerializer(max_bet).data,
                            "valid_bet": BidSerializer(bet).data,
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    bet.delete()
                    continue
            return Response(
                {"invalid_bet": BidSerializer(max_bet).data, "valid_bet": None},
                status=status.HTTP_200_OK,
            )


class AuctionEndView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="end if auction and take the greatest bet",
        responses={
            200: tx_response,
            400: error_response,
            404: TokenNotFound.default_detail,
        },
    )
    def post(self, request, token_id):
        token = Token.objects.filter(id=token_id).first()
        if not token:
            raise TokenNotFound

        max_bet = token.get_highest_bid()
        bet = token.exchange.get_valid_bid()
        if not bet or bet != max_bet:
            return Response({"error": "invalid bid"}, status=status.HTTP_404_NOT_FOUND)
        buyer = bet.user
        seller = request.user

        # TODO: move to validator?
        ownership = token.ownerships.filter(
            owner=seller,
            selling=True,
            minimal_bid__isnull=False,
        ).first()
        if not ownership:
            return Response(
                {"error": "user is not owner or token is not on sell"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if token.is_single:
            token_amount = 0
        else:
            token_amount = min(bet.quantity, ownership.quantity)

        initial_tx = token.exchange.buy(
            amount=token_amount,
            buyer=buyer,
            seller=seller,
            auction=True,
        )
        return Response({"initial_tx": initial_tx}, status=status.HTTP_200_OK)


class ReportView(APIView):
    @swagger_auto_schema(
        operation_description="report page",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "page": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="url to page user is currently on",
                ),
                "message": openapi.Schema(type=openapi.TYPE_STRING),
                "token": openapi.Schema(
                    type=openapi.TYPE_STRING, description="recaptcha token"
                ),
            },
            required=["page", "message", "token"],
        ),
        responses={200: "your report sent to admin", 400: "report not sent to admin"},
    )
    def post(self, request):
        """
        view for report form
        """
        request_data = request.data
        page = request_data.get("page")
        message = request_data.get("message")
        response = request_data.get("token")

        if config.CAPTCHA_SECRET:
            if not check_captcha(response):
                return Response(
                    "you are robot. go away, robot!", status=status.HTTP_400_BAD_REQUEST
                )

        text = """
                Page: {page}
                Message: {message}
                """.format(
            page=page, message=message
        )

        receiver = EmailConfig.get_admin_receiver()
        sender = EmailConfig.get_admin_sender()

        send_mail(
            f"Report from {config.TITLE}",
            text,
            sender.address,
            [receiver],
            connection=sender.connection(),
        )
        logging.info("message sent")

        return Response("OK", status=status.HTTP_200_OK)


class SetCoverView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="set cover",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_NUMBER),
                "cover": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY
                ),
            },
            required=["id", "cover"],
        ),
        responses={200: "OK", 400: "error"},
    )
    def post(self, request):
        user = request.user
        collection_id = request.data.get("id")
        collection = get_collection_by_short_url(collection_id)
        if collection.creator != user:
            return Response(
                {"error": "you can set covers only for your collections"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        media = request.FILES.get("cover")
        if media:
            ipfs = send_to_ipfs(media)
            collection.cover_ipfs = ipfs
            collection.save()
        return Response(collection.cover, status=status.HTTP_200_OK)


@swagger_auto_schema(
    methods=["get"],
    manual_parameters=[
        openapi.Parameter(
            "network",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="name of network",
        ),
    ],
    responses={200: TokenFullSerializer, 404: "Tokens not found"},
)
@api_view(http_method_names=["GET"])
@cache_page(60)
def get_favorites(request):
    network = request.query_params.get("network", None)
    token_list = Token.objects.committed().filter(
        Exists(
            Promotion.objects.filter(
                token__id=OuterRef("id"),
                status=Promotion.PromotionStatus.IN_PROGRESS,
            )
        )
    )
    if network:
        token_list = token_list.network(network)
    if len(token_list) > 4:
        token_list = random.shuffle(list(token_list))
    tokens = TokenFullSerializer(
        token_list,
        many=True,
        context={"user": request.user, "only_active": True},
    ).data
    return Response(tokens, status=status.HTTP_200_OK)


@swagger_auto_schema(
    methods=["get"],
    manual_parameters=[
        openapi.Parameter(
            "network",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="name of network",
        ),
    ],
    responses={200: TokenFullSerializer, 404: "No bids"},
)
@api_view(http_method_names=["GET"])
def get_hot_bids(request):
    network = request.query_params.get("network", config.DEFAULT_NETWORK)
    bids = (
        Bid.objects.filter(state=Status.COMMITTED)
        .filter(token__collection__network__name__icontains=network)
        .distinct("token")[:6]
    )
    if not bids.exists():
        return Response("No bids found", status=status.HTTP_404_NOT_FOUND)
    token_list = [bid.token for bid in bids]
    response_data = TokenFullSerializer(
        token_list,
        context={"user": request.user},
        many=True,
    ).data
    return Response(response_data, status=status.HTTP_200_OK)


class SupportView(APIView):
    @swagger_auto_schema(
        operation_description="support view",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "email": openapi.Schema(type=openapi.TYPE_STRING),
                "message": openapi.Schema(type=openapi.TYPE_STRING),
                "token": openapi.Schema(
                    type=openapi.TYPE_STRING, description="recaptcha token"
                ),
            },
            required=["email", "message", "token"],
        ),
        responses={200: "your report sent to admin", 400: "report not sent to admin"},
    )
    def post(self, request):
        """
        view for report form
        """
        request_data = request.data
        email = request_data.get("email")
        message = request_data.get("message")
        response = request_data.get("token")

        if config.CAPTCHA_SECRET:
            if not check_captcha(response):
                return Response(
                    "you are robot. go away, robot!", status=status.HTTP_400_BAD_REQUEST
                )

        text = """
                Email: {email}
                Message: {message}
                """.format(
            email=email, message=message
        )

        receiver = EmailConfig.get_admin_receiver()
        sender = EmailConfig.get_admin_sender()

        send_mail(
            f"Support form from {config.TITLE}",
            text,
            sender.address,
            [receiver],
            connection=sender.connection(),
        )
        logging.info("message sent")

        return Response("your report sent to admin", status=status.HTTP_200_OK)


class TransactionTrackerView(APIView):
    """
    View for transaction tracking
    """

    @swagger_auto_schema(
        operation_description="transaction_tracker",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "tx_hash": openapi.Schema(type=openapi.TYPE_STRING),
                "token": openapi.Schema(type=openapi.TYPE_NUMBER),
                "ownership": openapi.Schema(
                    type=openapi.TYPE_STRING, description="url of seller"
                ),
                "amount": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
            required=["tx_hash", "token", "ownership"],
        ),
        responses={200: success_response, 404: error_response},
    )
    def post(self, request):
        token_id = request.data.get("token")
        tx_hash = request.data.get("tx_hash")
        amount = request.data.get("amount", 1)
        bid_id = request.data.get("bid_id")

        token = Token.objects.filter(id=token_id).first()
        if not token:
            return Response(
                {"error": "token with given id not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        bid = None
        if bid_id:
            bid = Bid.objects.filter(id=bid_id).first()
            if not bid:
                return Response(
                    {"error": "bid not found"}, status=status.HTTP_404_NOT_FOUND
                )

        owner_url = request.data.get("ownership")
        try:
            user = AdvUser.objects.get_by_custom_url(owner_url)
        except ObjectDoesNotExist:
            return Response(
                {"error": "wrong owner url"}, status=status.HTTP_404_NOT_FOUND
            )
        ownership = Ownership.objects.filter(token_id=token_id, owner=user).first()
        tracker = TransactionTracker.objects.filter(
            token=token, ownership=ownership, amount=amount, bid=bid
        ).first()
        if tracker:
            tracker.tx_hash = tx_hash
            tracker.save()
            return Response(
                {"success": "transaction is tracked"}, status=status.HTTP_200_OK
            )
        return Response(
            {"error": "tracker not found"}, status=status.HTTP_404_NOT_FOUND
        )


@swagger_auto_schema(
    method="get",
    manual_parameters=[
        openapi.Parameter(
            "currency",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="symbol of currency",
        ),
        openapi.Parameter(
            "collection",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="url of collection",
        ),
        openapi.Parameter(
            "game",
            openapi.IN_QUERY,
            type=openapi.TYPE_NUMBER,
            description="game id",
        ),
        openapi.Parameter(
            "network",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="name of network",
        ),
    ],
    operation_description="get max price",
    responses={200: max_price_response},
)
@api_view(http_method_names=["GET"])
def get_max_price(request):
    network = request.query_params.get("network")
    currency = request.query_params.get("currency")
    collection = request.query_params.get("collection")
    game = request.query_params.get("game")
    owners = Ownership.objects.filter(selling=True)
    if network:
        owners = owners.filter(token__collection__network__name__iexact=network)
    if collection:
        try:
            collection = Collection.objects.get_by_short_url(collection)
        except ObjectDoesNotExist:
            raise CollectionNotFound
        owners = owners.filter(token__collection=collection)
    if game:
        try:
            game = GameCompany.objects.get(id=game)
        except ObjectDoesNotExist:
            raise GameCompanyNotFound
        owners = owners.filter(token__collection__game_subcategory__category__game=game)
    if not currency:
        prices = [
            o.price_or_minimal_bid_usd
            for o in owners
            if o.price_or_minimal_bid_usd is not None
        ]
        max_price = max(prices) if prices else 0
        return Response({"max_price": max_price}, status=status.HTTP_200_OK)
    owners = owners.filter(currency__symbol__iexact=currency)
    max_price = 0
    if owners:
        max_price = max(
            owners, key=lambda owner: owner.price_or_minimal_bid or 0
        ).price_or_minimal_bid
    return Response({"max_price": max_price or 0}, status=status.HTTP_200_OK)


class GetMostBiddedView(APIView):
    """
    View for get info for tokens with most bid count.
    """

    @swagger_auto_schema(
        operation_description="Return tokens with most bid count",
        responses={
            200: TokenFullSerializer(many=True),
            404: TokenNotFound.default_detail,
        },
    )
    def get(self, request):
        tokens = (
            Token.objects.committed()
            .annotate(bid_count=Count("bid"))
            .filter(bid_count__gt=0)
            .order_by("-bid_count")[:5]
        )
        if not tokens:
            return Response("tokens not found", status=status.HTTP_404_NOT_FOUND)
        response_data = TokenFullSerializer(
            tokens,
            many=True,
            context={"user": request.user},
        ).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetRelatedView(APIView):
    """
    View for get info for token related to id.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_description="Return 4 random tokens from current token collection",
        responses={
            200: TokenSlimSerializer(many=True),
            404: TokenNotFound.default_detail,
        },
    )
    def get(self, request, token_id):
        token = get_committed_token(token_id)
        random_related = (
            Token.objects.committed()
            .filter(collection=token.collection)
            .exclude(id=token_id)
            .distinct()
        )
        if random_related:
            random_related = random.choices(random_related, k=4)
            # if count of tokens is less than k, the list will contain duplicate
            random_related = set(random_related)
        response_data = TokenSlimSerializer(
            random_related,
            many=True,
            context={"user": request.user},
        ).data
        return Response(response_data, status=status.HTTP_200_OK)


class MintRejectView(APIView):
    """
    View for remove rejected token or collection by id.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Remove rejected token or collection",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_NUMBER),
                "type": openapi.Schema(
                    type=openapi.TYPE_STRING, description="token. collection"
                ),
            },
            required=["id", "type"],
        ),
        responses={200: "success", 400: error_response},
    )
    def post(self, request):
        items = {
            "token": Token,
            "collection": Collection,
        }
        item_type = request.data.get("type")
        item_id = request.data.get("id")
        if item_type not in ["token", "collection"]:
            return Response(
                {"error": "Item type should be 'token' or 'collection'"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item = (
            items[item_type]
            .objects.filter(
                status=Status.PENDING,
                id=item_id,
            )
            .first()
        )
        if item_type == "token":
            TransactionTracker.objects.filter(token__id=item_id).delete()
        if item:
            item.delete()
        return Response("success", status=status.HTTP_200_OK)


class BuyRejectView(APIView):
    """
    View for remove rejected buy token transaction.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Remove rejected buy token transaction",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_NUMBER),
                "owner": openapi.Schema(
                    type=openapi.TYPE_STRING, description="url of seller"
                ),
            },
            required=["id", "owner"],
        ),
        responses={200: "success"},
    )
    def post(self, request):
        item_id = request.data.get("id")
        owner_url = request.data.get("owner")
        transactions = TransactionTracker.objects.filter(token__id=item_id)
        try:
            owner = AdvUser.objects.get_by_custom_url(owner_url)
        except ObjectDoesNotExist:
            owner = None
        if owner is not None:
            owner = Ownership.objects.filter(token__id=item_id, owner=owner).first()
            transactions = transactions.filter(ownership=owner)
        for tx in transactions:
            if tx.ownership.selling_quantity == 0:
                tx.ownership.selling_quantity = tx.amount
            tx.ownership.selling = True
            tx.ownership.save()
            tx.delete()
        return Response("success", status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    manual_parameters=[
        openapi.Parameter(
            "network",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="name of network",
        ),
        openapi.Parameter(
            "category",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="name of category",
        ),
    ],
    operation_description="Trending collections",
    responses={200: TrendingCollectionSerializer(many=True)},
)
@api_view(http_method_names=["GET"])
def trending_collections(request):
    category = request.query_params.get("category")
    network = request.query_params.get("network")

    tracker_time = timezone.now() - timedelta(days=config.TRENDING_TRACKER_TIME)

    tracker = (
        ViewsTracker.objects.filter(created_at__gte=tracker_time)
        .filter(token=OuterRef("id"))
        .values("token")
        .annotate(views_=Count("id"))
    )

    tokens = (
        Token.objects.filter(collection=OuterRef("id"))
        .annotate(views_=Subquery(tracker.values("views_")[:1]))
        .values("collection")
        .annotate(views=Sum("views_"))
    )
    collections = (
        Collection.objects.network(network)
        .category(category)
        .filter(is_default=False)
        .annotate(views=Subquery(tokens.values("views")[:1]))
    ).order_by("-views")
    collections = [col for col in collections if col.views][:12]
    return Response(
        TrendingCollectionSerializer(collections, many=True).data,
        status=status.HTTP_200_OK,
    )


@swagger_auto_schema(
    method="get",
    manual_parameters=[
        openapi.Parameter(
            "category",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="category name",
        ),
    ],
    operation_description="Trending tokens",
    responses={200: TokenSerializer(many=True)},
)
@api_view(http_method_names=["GET"])
@cache_page(60)
def trending_tokens(request):
    """Return 12 tokens sotred by likes"""
    category = request.query_params.get("category")
    tokens = (
        Token.objects.committed()
        .filter(
            Exists(UserAction.objects.filter(token__id=OuterRef("id"), method="like"))
        )
        .filter(
            Exists(Ownership.objects.filter(token__id=OuterRef("id"), selling=True))
        )
    )
    if category:
        tokens = tokens.filter(category__name__iexact=category)
    tokens = sorted(
        tokens,
        key=lambda token: token.likes.count(),
        reverse=True,
    )
    tokens = list(tokens)[:12]
    return Response(
        TokenSerializer(tokens, many=True, context={"user": request.user}).data,
        status=status.HTTP_200_OK,
    )


class FastSearchTokenView(APIView):
    @swagger_auto_schema(
        operation_description="presearch",
        manual_parameters=[
            openapi.Parameter(
                "presearch",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="presearch",
                required=True,
            ),
        ],
        responses={200: FastSearchSerializer},
    )
    def get(self, request, *args, **kwargs):
        presearch = self.request.query_params.get("presearch")
        tokens = Token.objects.committed().filter(name__icontains=presearch)
        tokens = TokenFastSearchSerializer(tokens[:8], many=True).data
        users = AdvUser.objects.filter(display_name__icontains=presearch)
        users = UserSlimSerializer(users[:8], many=True).data
        collections = Collection.objects.committed().filter(name__icontains=presearch)
        collections = CollectionFastSearchSerializer(collections[:8], many=True).data

        response = {"tokens": tokens, "users": users, "collections": collections}
        return Response(response, status=status.HTTP_200_OK)
