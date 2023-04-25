from django.apps import AppConfig


class PromotionConfig(AppConfig):
    name = "src.promotion"

    def ready(self):
        from . import signals
