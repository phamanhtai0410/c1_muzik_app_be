from django.apps import AppConfig


class AccountConfig(AppConfig):
    name = "src.accounts"

    def ready(self):
        from . import signals
