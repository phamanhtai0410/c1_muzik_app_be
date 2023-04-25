import os

from django.urls import path

from src.accounts.views import (
    FollowView,
    GetFollowersView,
    GetFollowingView,
    GetLikedView,
    GetOtherView,
    GetUserCollections,
    GetView,
    GetWebSocketToken,
    LikeView,
    SecureMetamaskLogin,
    SetUserCoverView,
    UnfollowView,
    generate_metamask_message,
    sign_message,
)
from src.settings import config

urlpatterns = [
    path("metamask_login/", SecureMetamaskLogin.as_view(), name="metamask_login"),
    path("get_metamask_message/<str:address>/", generate_metamask_message),
    path("self/follow/", FollowView.as_view()),
    path("self/unfollow/", UnfollowView.as_view()),
    path("self/like/", LikeView.as_view()),
    path("self/collections/", GetUserCollections.as_view()),
    path("self/set_cover/", SetUserCoverView.as_view()),
    path("self/", GetView.as_view()),
    path("<str:user_id>/", GetOtherView.as_view()),
    path("<str:user_id>/liked/", GetLikedView.as_view()),
    path("<str:user_id>/following/", GetFollowingView.as_view()),
    path("<str:user_id>/followers/", GetFollowersView.as_view()),
]

if config.DEBUG:
    urlpatterns.insert(1, path("sign_message/", sign_message))

ws_urls = [
    path("self/get_ws_token/", GetWebSocketToken.as_view()),
]

if os.getenv("USE_WS") and os.getenv("USE_WS") == "True":
    urlpatterns.extend(ws_urls)
