from typing import Dict

from src.accounts.models import AdvUser
from src.settings import config


class Subscriptor:
    enable_following_notifications = config.INCLUDE_FOLLOWING_NOTIFICATIONS

    @classmethod
    def add_subscriptors(cls, receiver: "AdvUser") -> Dict["AdvUser", str]:
        # if enabled, get all user followers, else return empty list
        additional_receivers = {}
        if cls.enable_following_notifications:
            additional_receivers = dict.fromkeys(
                AdvUser.objects.filter(followers__whom_follow=receiver).distinct(),
                "follow",
            )
        return additional_receivers
