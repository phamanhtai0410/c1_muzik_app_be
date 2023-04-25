import json
import logging

from src.accounts.models import AdvUser
from src.activity.models import ActivitySubscription

from .router import get_router

router = get_router()


def parse_event_data(message):
    message_data = json.loads(message.get("data"))
    user_url = message.get("user_url")
    return message_data, user_url


@router.register("new_collection")
def new_collection(message):
    print(f"Received new collection event. Data: {message}")
    return True


@router.register("notifications")
def notifications(message):
    print(f"Received new notification event. Data: {message}")
    message_data, user_url = parse_event_data(message)

    activity_ids = message_data.get("activity_ids")
    method = message_data.get("method")

    user = AdvUser.objects.get_by_custom_url(user_url)

    if method == "all":
        ActivitySubscription.objects.filter(receiver=user).update(is_viewed=True)
        logging.info("Marked all as viewed")
        return

    ActivitySubscription.objects.filter(id__in=activity_ids, receiver=user).update(
        is_viewed=True
    )
    logging.info("Marked as viewed")
    return
