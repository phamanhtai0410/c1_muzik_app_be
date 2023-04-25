from django.urls import path

from src.networks.views import NetworksModelView

urlpatterns = [
    path(
        "",
        NetworksModelView.as_view({"get": "list"}),
    ),
    path(
        "<str:name>",
        NetworksModelView.as_view({"get": "retrieve"}),
    ),
]
