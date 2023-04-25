import logging
from time import sleep

from django.core.mail import EmailMultiAlternatives

from celery import shared_task
from src.mail_subscription.models import SubscriptionMail
from src.support.models import EmailConfig


@shared_task(name="send_subsrcriber_mail_executer")
def send_subscriber_mail_executer(message_id: int, user_address: str):

    sender = EmailConfig.get_admin_sender()
    try:
        message = SubscriptionMail.objects.get(pk=message_id)
    except SubscriptionMail.DoesNotExist:
        # retry to fetch from db because race
        sleep(5)
        message = SubscriptionMail.objects.get(pk=message_id)

    mail = EmailMultiAlternatives(
        subject=message.title,
        body=message.processed_text,
        from_email=sender.address,
        to=[user_address],
        connection=sender.connection(),
    )
    mail.content_subtype = "html"
    # mail.attach_alternative(message.text.plain, "text/plain")
    mail.send(fail_silently=False)

    logging.info("message sent")
