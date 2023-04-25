from django.apps import AppConfig


class NetworksConfig(AppConfig):
    name = "src.networks"

    def ready(self):
        from . import signals
