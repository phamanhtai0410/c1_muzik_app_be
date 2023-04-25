from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.activity.serializers import (
    ActivitySerializer,
    PaginateActivitySerializer,
    UserStatSerializer,
)
from src.activity.services.activity import Activity
from src.activity.services.top_collections import get_top_collections
from src.activity.services.top_users import get_top_users
from src.networks.models import Network
from src.responses import error_response
from src.settings import config
from src.store.serializers import PaginateTopCollectionsSerializer
from src.store.utils import get_collection_by_short_url
from src.utilities import PaginateMixin

from .models import ActivitySubscription


class ActivityView(APIView, PaginateMixin):
    """
    View for get activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get activity",
        manual_parameters=[
            openapi.Parameter(
                "network",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="name of the network",
            ),
            openapi.Parameter(
                "type",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Buy, Transfer, Mint, Burn, Listing, like, follow, Bet, AuctionWin",
            ),
            openapi.Parameter(
                "items_per_page", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "currency",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="list of comma-separated currency symbols",
            ),
        ],
        responses={200: PaginateActivitySerializer},
    )
    def get(self, request):
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        types = request.query_params.get(
            "type",
            "Buy, Transfer, Mint, Burn, Listing, like, follow, Bet, AuctionWin",
        ).replace(" ", "")
        activities = Activity(
            network=network,
            types=types.split(","),
        ).get_activity()
        return Response(
            self.paginate(request, activities, ActivitySerializer),
            status=status.HTTP_200_OK,
        )


class NotificationActivityView(APIView):
    """
    View for get user notifications
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="get user notifications, return last 5",
        manual_parameters=[
            openapi.Parameter(
                "network",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="name of the network",
            ),
        ],
        responses={200: ActivitySerializer},
    )
    def get(self, request):
        address = request.user.username
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        types_list = ["Transfer", "Mint", "Burn", "Buy", "Listing", "AuctionWin"]

        activities = Activity(
            network=network,
            types=types_list,
            user=address.lower(),
            hide_viewed=True,
            filter_type="self",
        ).get_activity()
        response_data = ActivitySerializer(
            activities[: config.NOTIFICATION_COUNT], many=True
        ).data
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Mark activity as viewed. Method 'all' - marked all activity as viewed.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "activity_ids": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_NUMBER),
                ),
                "method": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: "Marked as viewed"},
    )
    def post(self, request):
        method = request.data.get("method")
        if method == "all":
            ActivitySubscription.objects.filter(receiver=request.user).update(
                is_viewed=True
            )
            return Response("Marked all as viewed", status=status.HTTP_200_OK)
        activity_ids = request.data.get(
            "activity_ids"
        )  # check with QA if just "get" is working on DEV
        if not isinstance(activity_ids, list):
            activity_ids = request.data.getlist(
                "activity_ids"
            )  # check with QA if just "get" is working on DEV
        ActivitySubscription.objects.filter(
            id__in=activity_ids, receiver=request.user
        ).update(is_viewed=True)
        return Response("Marked as viewed", status=status.HTTP_200_OK)


class UserActivityView(APIView, PaginateMixin):
    """
    View for get users activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get user activity",
        manual_parameters=[
            openapi.Parameter(
                "network",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="name of the network",
            ),
            openapi.Parameter(
                "type",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Buy, Transfer, Mint, Burn, Listing, like, follow, Bet, AuctionWin",
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "items_per_page", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
        ],
        responses={200: PaginateActivitySerializer},
    )
    def get(self, request, address):
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        types = request.query_params.get(
            "type",
            "Buy,Transfer,Mint,Burn,Listing,like,follow,Bet,AuctionWin",
        ).replace(" ", "")

        activities = Activity(
            network=network,
            types=types.split(","),
            user=address.lower(),
            filter_type="self",
        ).get_activity()

        return Response(
            self.paginate(request, activities, ActivitySerializer),
            status=status.HTTP_200_OK,
        )


class CollectionActivityView(APIView, PaginateMixin):
    """
    View for get users activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get user activity",
        manual_parameters=[
            openapi.Parameter(
                "type",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Sales,Transfer,Listing,Bet",
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "items_per_page", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
        ],
        responses={200: PaginateActivitySerializer},
    )
    def get(self, request, param):
        collection = get_collection_by_short_url(param)
        types = request.query_params.get("type", "Sales,Transfer,Listing,Bet").replace(
            " ", ""
        )
        if "Sales" in types:
            types = types.replace("Sales", "Buy, AuctionWin")

        activities = Activity(
            network=collection.network,
            types=types.split(","),
            collection=collection,
        ).get_activity()

        return Response(
            self.paginate(request, activities, ActivitySerializer),
            status=status.HTTP_200_OK,
        )


class FollowingActivityView(APIView, PaginateMixin):
    """
    View for get user following activities and filter by types
    """

    @swagger_auto_schema(
        operation_description="get user activity",
        manual_parameters=[
            openapi.Parameter(
                "network",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="name of the network",
            ),
            openapi.Parameter(
                "type",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Buy, Transfer, Mint, Burn, Listing, like, follow, Bet, AuctionWin",
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={200: PaginateActivitySerializer},
    )
    def get(self, request, address):
        network = request.query_params.get("network", config.DEFAULT_NETWORK)
        types = request.query_params.get(
            "type", "Buy, Transfer, Mint, Burn, Listing, like, follow, Bet, AuctionWin"
        ).replace(" ", "")
        activities = Activity(
            network=network,
            types=types.split(","),
            user=address.lower(),
            filter_type="follow",
        ).get_activity()

        return Response(
            self.paginate(request, activities, ActivitySerializer),
            status=status.HTTP_200_OK,
        )


class GetTopCollectionsView(APIView, PaginateMixin):
    @swagger_auto_schema(
        operation_description="get top collections",
        manual_parameters=[
            openapi.Parameter(
                "network",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="name of the network",
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "items_per_page", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
        ],
        responses={200: PaginateTopCollectionsSerializer, 400: error_response},
    )
    def get(self, request):
        network = request.query_params.get("network")
        collections = get_top_collections(network)
        return Response(self.paginate(request, collections), status=status.HTTP_200_OK)


class GetTopUsersView(APIView):
    @swagger_auto_schema(
        operation_description="get top users",
        manual_parameters=[
            openapi.Parameter("network", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={200: UserStatSerializer(many=True)},  # TODO paginate?
    )
    def get(self, request):
        network_name = request.query_params.get("network", None)
        network = None
        if network_name:
            network = Network.objects.filter(name__icontains=network_name).first()

        top_users_data = get_top_users(network)
        return Response(top_users_data, status=status.HTTP_200_OK)
