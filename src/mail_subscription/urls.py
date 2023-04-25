from django.urls import path

from src.mail_subscription.views import UserSubscriptionDeleteView, UserSubscriptionView

urlpatterns = [
    path(
        "",
        UserSubscriptionView.as_view({"post": "create"}),
    ),
    path("unsubscribe/", UserSubscriptionDeleteView.as_view()),
]
