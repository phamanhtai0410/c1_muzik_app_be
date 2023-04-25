import asyncio
import json
import logging
import os
import sys

import aioredis

import websockets

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.settings")
import django

django.setup()

from sesame.utils import get_user

from src.settings import config
from src.websockets.event_sender import EventSender

CONNECTIONS = {}
WS_USERS = {}

redis = aioredis.from_url(f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/0")
pubsub = redis.pubsub()


async def authorize(websocket):
    """Authorization"""
    loop = asyncio.get_running_loop()
    sesame = await websocket.recv()

    user = await loop.run_in_executor(None, get_user, sesame)
    if user is None:
        await websocket.close(1011, "authentication failed")
        return

    CONNECTIONS[user.url] = websocket
    WS_USERS[websocket] = user.url
    logging.info(f"Authorized {user.url} - {websocket}")

    return user


async def listen_user_messages(websocket):
    """Listen to messages of ws client"""
    async for message in websocket:
        logging.info(f"new user message: {message}")
        user_url = WS_USERS.get(websocket)
        event_sender = EventSender(message, user_url, redis)
        sent, error_msg = await event_sender.publish()
        if not sent:
            await websocket.send(json.dumps({"error": error_msg}))


async def process_events():
    """Listen to events in Redis and process them."""
    logging.info("Listen events handler")
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        payload = message["data"].decode()
        logging.info(f"payload: {payload}")

        event = json.loads(payload)
        if isinstance(event, str):
            event = json.loads(event)

        if "ws_client_id" not in event:
            continue

        recipients = []
        event_client_id = event["ws_client_id"]
        if event_client_id in CONNECTIONS.keys():
            recipients.append(CONNECTIONS[event_client_id])

        websockets.broadcast(recipients, payload)


async def main_handler(websocket):
    """Authorize user and run two parallel tasks for send/receive"""
    user = await authorize(websocket)

    try:
        await asyncio.gather(listen_user_messages(websocket), process_events())

        await websocket.wait_closed()

    finally:
        if user:
            del CONNECTIONS[user.url]


async def main():
    await pubsub.subscribe("websocket_events")
    logging.info("Subscribed to redis")
    async with websockets.serve(main_handler, "0.0.0.0", 8001):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
