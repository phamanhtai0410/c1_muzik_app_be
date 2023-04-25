from django.apps import AppConfig


class StoreConfig(AppConfig):
    name = "src.store"

    def ready(self):
        from . import signals
