from django.urls import path

from src.promotion.views import PromotionView

urlpatterns = [
    path("", PromotionView.as_view({"get": "list", "post": "create"})),
]
