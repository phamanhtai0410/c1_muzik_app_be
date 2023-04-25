from django.urls import path

from src.activity import views

urlpatterns = [
    path("topusers/", views.GetTopUsersView.as_view()),
    path("top-collections/", views.GetTopCollectionsView.as_view()),
    path("notification/", views.NotificationActivityView.as_view()),
    path("", views.ActivityView.as_view()),
    path("collections/<str:param>/", views.CollectionActivityView.as_view()),
    path("<str:address>/", views.UserActivityView.as_view()),
    path("<str:address>/following/", views.FollowingActivityView.as_view()),
]
