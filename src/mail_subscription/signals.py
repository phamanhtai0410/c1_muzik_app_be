from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from src.mail_subscription.models import SubscriptionMail, SubscriptionUser
from src.mail_subscription.tasks import send_subscriber_mail_executer


@receiver(pre_save, sender=SubscriptionMail)
def subscribe_mail_pre_save_dispatcher(sender, instance, *args, **kwargs):
    instance.process_html()


@receiver(post_save, sender=SubscriptionMail)
def subscribe_mail_post_save_dispatcher(sender, instance, created, *args, **kwargs):

    if instance.processed_text and created:
        receivers = SubscriptionUser.objects.all()

        for r in receivers:
            send_subscriber_mail_executer.apply_async(
                args=(instance.pk, r.email_address), priority=5
            )
