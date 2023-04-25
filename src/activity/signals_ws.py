from django.db.models.signals import post_save
from django.dispatch import receiver

from src.activity.models import ActivitySubscription
from src.activity.services.ws_signal_sender import SignalSender


@receiver(post_save, sender=ActivitySubscription)
def publish_event_user_action(sender, instance, created, *args, **kwargs):
    if created and instance.valid_for_notification:
        signal_sender = SignalSender(instance)
        signal_sender.send()
