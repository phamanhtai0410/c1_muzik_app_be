import json
import logging

from django.core.mail import send_mail

from celery import shared_task
from src.support.models import EmailConfig
from src.utilities import RedisClient


@shared_task(name="send_email_notification")
def send_email_notification(redis_key) -> None:
    connection = RedisClient().connection
    cached_data = connection.get(redis_key)
    if not cached_data:
        return
    data = json.loads(cached_data)
    topic = data.get("topic")
    text = data.get("text")
    receiver = data.get("receiver")
    print(f"sending email {topic} {text} for {receiver}")
    # check for None in data
    if not text or not receiver:
        logging.warning(f"Invalid data: {text}, {receiver}")
        return
    sender_instance = EmailConfig.get_admin_sender()
    if not sender_instance:
        logging.warning("Sender not found, skipping")
        return
    connection = sender_instance.connection()
    send_mail(
        topic,
        "",
        sender_instance.address,
        [receiver],
        connection=connection,
        html_message=text,
    )
    logging.info(f"message {topic} to {receiver} sent")
