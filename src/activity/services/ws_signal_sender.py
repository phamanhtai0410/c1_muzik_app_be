import json
from decimal import Decimal

from src.activity.serializers import ActivitySerializer
from src.settings import USE_WS
from src.utilities import RedisClient


class SignalSender:

    serializer_from_field = "from_id"
    serializer_to_field = "to_id"

    def __init__(self, instance):
        self.instance = instance
        self.payload_data = None
        self.method = None
        self.ws_clients_id = instance.receiver.url

    def parse_instance(self):
        action_serializer = ActivitySerializer(self.instance)
        self.payload_data = action_serializer.data

        # cast decimals to float
        for key, value in self.payload_data.items():
            if isinstance(value, Decimal):
                self.payload_data[key] = str(value)

        self.method = self.payload_data.get("method")

    def send_to_redis(self, payload_data):
        redis = RedisClient()
        payload = json.dumps(payload_data)
        redis.connection.publish("websocket_events", payload)

    def send_to_websocket(self):
        payload = self.payload_data
        payload["ws_client_id"] = self.ws_clients_id
        self.send_to_redis(payload)

    def send(self):
        if not USE_WS:
            return

        self.parse_instance()
        self.send_to_websocket()
