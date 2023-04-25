from django.urls import path

from src.rates.views import RateRequest

urlpatterns = [
    path("", RateRequest.as_view()),
]
