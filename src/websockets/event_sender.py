import json
import logging
from inspect import getmembers, isfunction
from typing import Any

from aioredis.client import Redis

from events_catcher import events


def get_available_actions():
    actions = []
    members = getmembers(events, isfunction)
    for member in members:
        if member[1].__module__ == events.__name__:
            actions.append(member[0])
    return actions


class EventSender:
    def __init__(self, message: str, user_url: Any, redis: Redis):
        self.redis = redis
        self.user_url = user_url
        self.message = message

    async def publish(self) -> (bool, str):
        try:
            json_message = json.loads(self.message)
        except json.decoder.JSONDecodeError as e:
            logging.error(f"Cannot process message: {e} ({self.message})")
            return False, f"JSON Decode error: {e}"

        if ["action", "data"] != list(json_message.keys()):
            return False, "Fields: action, data are required for message"

        action = json_message.get("action")
        data = json_message.get("data")

        available_actions = get_available_actions()
        if action not in available_actions:
            return False, f"Action {action} is not supported"

        event = {"data": json.dumps(data), "user_url": self.user_url}
        logging.info(type(event), event)

        await self.redis.xadd(name=action, fields=event)
        return True, ""
