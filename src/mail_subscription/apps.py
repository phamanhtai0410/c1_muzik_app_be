from django.apps import AppConfig


class MailSubscriptionConfig(AppConfig):
    name = "src.mail_subscription"

    def ready(self):
        from . import signals
