from random import choice
from string import ascii_letters

from django.contrib.auth import login
from django.core.exceptions import ObjectDoesNotExist
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from eth_account.messages import encode_defunct
from knox.views import LoginView as KnoxLoginView
from rest_framework import status
from rest_framework.authentication import BasicAuthentication
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from sesame.utils import get_token
from web3 import Web3
from web3.auto import w3

from src.accounts.exceptions import SignatureInvalid, UserNotFound
from src.accounts.models import AdvUser
from src.accounts.serializers import (
    MetamaskLoginSerializer,
    PaginateUserFollowSerializer,
    PatchSerializer,
    UserFollowSerializer,
    UserSerializer,
    UserSlimSerializer,
)
from src.activity.models import UserAction
from src.responses import error_response
from src.settings import AUTHENTICATION_BACKENDS
from src.store.exceptions import TokenNotFound
from src.store.models import Collection
from src.store.serializers import (
    CompositeCollectionSerializer,
    PaginateCompositeCollectionSerializer,
    PaginateTokenSlimSerializer,
    TokenSlimSerializer,
)
from src.store.services.ipfs import send_to_ipfs
from src.store.utils import get_committed_token
from src.utilities import PaginateMixin


class SecureMetamaskLogin(KnoxLoginView):
    permission_classes = (AllowAny,)
    authentication_classes = [BasicAuthentication]

    @swagger_auto_schema(
        operation_description="Login",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "address": openapi.Schema(type=openapi.TYPE_STRING),
                "signed_msg": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "token": openapi.Schema(type=openapi.TYPE_STRING),
                    "expiry": openapi.Schema(type=openapi.TYPE_STRING),
                },
            ),
            400: SignatureInvalid.default_detail,
            404: TokenNotFound.default_detail,
        },
    )
    def post(self, request, format=None):
        serializer = MetamaskLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user, backend=AUTHENTICATION_BACKENDS[0])
        return super(SecureMetamaskLogin, self).post(request, format=None)


@swagger_auto_schema(
    method="get",
    operation_description="get message for login",
    responses={200: "string", 400: "invalid address"},
)
@api_view(http_method_names=["GET"])
def generate_metamask_message(request, address):
    if not Web3.isAddress(address):
        return Response("invalid address", status=status.HTTP_400_BAD_REQUEST)
    generated_message = "".join(choice(ascii_letters) for _ in range(30))
    request.session["metamask_message"] = generated_message
    try:
        user = AdvUser.objects.get(username__iexact=address)
    except AdvUser.DoesNotExist:
        user = AdvUser.objects.create(username=address.lower())
    user.metamask_message = generated_message
    user.save(update_fields=("metamask_message",))
    return Response(generated_message)


class GetView(APIView):
    """
    view for getting and patching user info
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="get self info",
        responses={200: UserSerializer},
    )
    def get(self, request):
        response_data = UserSerializer(request.user).data
        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Update current user info",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "display_name": openapi.Schema(type=openapi.TYPE_STRING),
                "avatar": openapi.Schema(type=openapi.TYPE_OBJECT),
                "bio": openapi.Schema(type=openapi.TYPE_STRING),
                "custom_url": openapi.Schema(type=openapi.TYPE_STRING),
                "email": openapi.Schema(type=openapi.FORMAT_EMAIL),
                "twitter": openapi.Schema(type=openapi.TYPE_STRING),
                "instagram": openapi.Schema(type=openapi.TYPE_STRING),
                "facebook": openapi.Schema(type=openapi.TYPE_STRING),
                "site": openapi.Schema(type=openapi.TYPE_STRING),
                "cover": openapi.Schema(
                    type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY
                ),
            },
        ),
        responses={200: UserSlimSerializer, 400: error_response},
    )
    def patch(self, request):
        user = request.user

        media = request.FILES.get("cover")
        if media:
            request.data.pop("cover", None)

        avatar = request.FILES.get("avatar")
        is_remove_avatar = request.data.get("avatar", "not null") == "null"
        request_data = request.data.copy()
        if avatar:
            request_data["avatar_ipfs"] = send_to_ipfs(avatar)
        if media:
            request_data["cover_ipfs"] = send_to_ipfs(media)
        if request_data.get("custom_url") == "":
            request_data.pop("custom_url")

        serializer = PatchSerializer(user, data=request_data, partial=True)

        if serializer.is_valid():
            result = serializer.save()
        if serializer.errors:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # unique constraint handling:
        if isinstance(result, dict):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        if is_remove_avatar:
            user.avatar_ipfs = None
            user.save()
        response_data = UserSlimSerializer(user).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetLikedView(APIView, PaginateMixin):
    """
    View for getting all items liked by address
    """

    @swagger_auto_schema(
        operation_description="get tokens liked by address",
        responses={200: PaginateTokenSlimSerializer, 404: UserNotFound.default_detail},
        manual_parameters=[
            openapi.Parameter(
                "network",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="name of the network",
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
            openapi.Parameter(
                "items_per_page", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
        ],
    )
    def get(self, request, user_id):
        network = request.query_params.get("network")
        try:
            user = AdvUser.objects.get_by_custom_url(user_id)
        except ObjectDoesNotExist:
            raise UserNotFound

        # get tokens that user like
        tokens_action = UserAction.objects.filter(
            method="like",
            user=user,
        ).order_by("-date")
        if network and network != "undefined":
            tokens_action = tokens_action.filter(
                token__collection__network__name__icontains=network
            )

        tokens = [action.token for action in tokens_action]
        return Response(
            self.paginate(request, tokens, TokenSlimSerializer, {"user": request.user}),
            status=status.HTTP_200_OK,
        )


class GetOtherView(APIView):
    """
    view for getting other user info
    """

    @swagger_auto_schema(
        operation_description="get other user's info",
        responses={200: UserSerializer, 404: UserNotFound.default_detail},
    )
    def get(self, request, user_id):
        try:
            user = AdvUser.objects.get_by_custom_url(user_id)
        except ObjectDoesNotExist:
            raise UserNotFound
        response_data = UserSerializer(user, context={"user": request.user}).data
        return Response(response_data, status=status.HTTP_200_OK)


class FollowView(APIView):
    """
    View for following another user.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="follow user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(
                    type=openapi.TYPE_NUMBER, description="user's 'url'"
                ),
            },
            required=["id"],
        ),
        responses={
            200: "Followed",
            400: error_response,
            404: UserNotFound.default_detail,
        },
    )
    def post(self, request):
        follower = request.user
        request_data = request.data
        id_ = request_data.get("id")

        try:
            user = AdvUser.objects.get_by_custom_url(id_)
        except ObjectDoesNotExist:
            raise UserNotFound

        if follower == user:
            return Response(
                {"error": "you cannot follow yourself"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        UserAction.objects.get_or_create(user=follower, whom_follow=user)
        return Response("Followed", status=status.HTTP_200_OK)


class UnfollowView(APIView):
    """
    View for unfollowing another user.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="unfollow user",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(
                    type=openapi.TYPE_NUMBER, description="user's 'url'"
                ),
            },
            required=["id"],
        ),
        responses={200: "Unfollowed", 404: UserNotFound.default_detail},
    )
    def post(self, request):
        follower = request.user
        request_data = request.data
        id_ = request_data.get("id")

        try:
            user = AdvUser.objects.get_by_custom_url(id_)
        except ObjectDoesNotExist:
            raise UserNotFound

        UserAction.objects.filter(whom_follow=user, user=follower).delete()
        return Response("Unfollowed", status=status.HTTP_200_OK)


class LikeView(APIView):
    """
    View for liking token.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="like token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "id": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
            required=["id"],
        ),
        responses={200: "liked/unliked", 404: TokenNotFound.default_detail},
    )
    def post(self, request):
        request_data = request.data
        token_id = request_data.get("id")

        item = get_committed_token(token_id)

        like, created = UserAction.objects.get_or_create(
            user=request.user, whom_follow=None, method="like", token=item
        )

        if created is False:
            like.delete()
            return Response("unliked", status=status.HTTP_200_OK)
        return Response("liked", status=status.HTTP_200_OK)


class GetUserCollections(APIView, PaginateMixin):
    """
    View for get collections by user
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="get collections by user",
        manual_parameters=[
            openapi.Parameter(
                "network",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="name of the network",
            ),
            openapi.Parameter(
                "items_per_page", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("standard", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={200: PaginateCompositeCollectionSerializer},
    )
    def get(self, request):
        network = request.query_params.get("network")
        standard = request.query_params.get("standard") or request.query_params.get(
            "standart"
        )  # reverse compatibility
        collections = Collection.objects.committed().user_collections(request.user)
        if network:
            collections = collections.filter(network__name__icontains=network)
        if standard:
            collections = collections.filter(standard=standard)
        return Response(
            self.paginate(request, collections, CompositeCollectionSerializer),
            status=status.HTTP_200_OK,
        )


class GetFollowingView(APIView, PaginateMixin):
    """
    View for getting active tokens of following users
    """

    @swagger_auto_schema(
        operation_description="post search pattern",
        manual_parameters=[
            openapi.Parameter(
                "items_per_page", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={
            200: PaginateUserFollowSerializer,
            404: UserNotFound.default_detail,
        },
    )
    def get(self, request, user_id):
        try:
            user = AdvUser.objects.get_by_custom_url(user_id)
        except ObjectDoesNotExist:
            raise UserNotFound

        follow_queryset = UserAction.objects.filter(method="follow", user=user)
        users = [action.whom_follow for action in follow_queryset]
        return Response(
            self.paginate(request, users, UserFollowSerializer),
            status=status.HTTP_200_OK,
        )


class GetFollowersView(APIView, PaginateMixin):
    """
    View for getting active tokens of following users
    """

    @swagger_auto_schema(
        operation_description="post search pattern",
        manual_parameters=[
            openapi.Parameter(
                "items_per_page", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={
            200: PaginateUserFollowSerializer,
            404: UserNotFound.default_detail,
        },
    )
    def get(self, request, user_id):
        try:
            user = AdvUser.objects.get_by_custom_url(user_id)
        except ObjectDoesNotExist:
            raise UserNotFound

        follow_queryset = UserAction.objects.filter(method="follow", whom_follow=user)
        followers_users = [action.user for action in follow_queryset]
        return Response(
            self.paginate(request, followers_users, UserFollowSerializer),
            status=status.HTTP_200_OK,
        )


class GetWebSocketToken(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="get short-lived token for websocket connection",
        responses={200: "string"},
    )
    def get(self, request):
        token = get_token(request.user)
        return Response(token, status=status.HTTP_200_OK)


class SetUserCoverView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="set cover",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "cover": openapi.Schema(type=openapi.FORMAT_BINARY),
            },
        ),
        responses={200: "cover_url"},
    )
    def post(self, request):
        user = request.user
        media = request.FILES.get("cover")
        ipfs = None
        if media:
            ipfs = send_to_ipfs(media)
        user.cover_ipfs = ipfs
        user.save()
        return Response(user.cover, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="post",
    operation_description="sign message for debug login",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "message": openapi.Schema(type=openapi.TYPE_STRING),
            "private_key": openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=["message", "private_key"],
    ),
    responses={200: "signature"},
)
@api_view(http_method_names=["POST"])
def sign_message(request):
    message = request.data.get("message")
    priv_key = request.data.get("private_key")
    message = encode_defunct(text=message)
    signed_message = w3.eth.account.sign_message(message, private_key=priv_key)
    return Response(signed_message.get("signature").hex(), status=status.HTTP_200_OK)
