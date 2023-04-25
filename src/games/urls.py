from django.urls import path

from src.games.views import (
    AddCollectionInSubCategoryView,
    CreateGameCategoryView,
    CreateGameSubCategoryView,
    CreateView,
    DeleteCategoryView,
    DeleteCollectionView,
    DeleteSubCategoryView,
    GameListView,
    GetGameCategoryView,
    GetGameSubCategoryView,
    GetGameView,
    UserGameListView,
)

urlpatterns = [
    path("", GameListView.as_view()),
    path("listing/", CreateView.as_view()),
    path("owned/", UserGameListView.as_view()),
    path("category/<int:category_id>/", DeleteCategoryView.as_view()),
    path("subcategory/<int:subcategory_id>/", DeleteSubCategoryView.as_view()),
    path("collection/<int:collection_id>/", DeleteCollectionView.as_view()),
    path("<str:game_name>/<str:network>/", GetGameView.as_view()),
    path(
        "<str:game_name>/<str:network>/category/<str:category_name>/",
        GetGameCategoryView.as_view(),
    ),
    path(
        "<str:game_name>/<str:network>/category_add/", CreateGameCategoryView.as_view()
    ),
    path(
        "<str:game_name>/<str:network>/category/<str:category_name>/subcategory/<str:subcategory_name>/",
        GetGameSubCategoryView.as_view(),
    ),
    path(
        "<str:game_name>/<str:network>/category/<str:category_name>/subcategory/<str:subcategory_name>/collection_add/",
        AddCollectionInSubCategoryView.as_view(),
    ),
    path(
        "<str:game_name>/<str:network>/category/<str:category_name>/subcategory_add/",
        CreateGameSubCategoryView.as_view(),
    ),
]
