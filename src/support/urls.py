from django.urls import path

from src.support.views import get_config_data

urlpatterns = [
    path("", get_config_data),
]
