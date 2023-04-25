import time

from src.utilities import RedisClient

from .events import router


class EventCatcher:
    def __init__(self):
        self._redis = RedisClient().connection
        self.router = router

    def handle_message(self, group, stream, msg):
        if hasattr(stream, "decode"):
            stream = stream.decode("utf-8")
        handler = self.router.routes.get(stream)

        if handler:
            msg_key, msg_value = msg

            try:
                is_success = handler(msg_value)

                if is_success:
                    self._redis.xack(stream, group, msg_key)
            except Exception as ex:
                print(ex)
        else:
            print(f"handler for stream: {stream} not found")

    def handle_pending_messages(self, group, streams):
        for stream in streams:
            pending_messages_info = self._redis.xpending(stream, group)

            if pending_messages_info.get("min") and pending_messages_info.get("max"):
                pending_messages = self._redis.xrange(
                    stream,
                    pending_messages_info.get("min"),
                    pending_messages_info.get("max"),
                )

                for msg in pending_messages:
                    self.handle_message(group, stream, msg)

    def parse_messages(self, group, consumer, streams):
        _streams = {s: ">" for s in streams}
        stream_messages = self._redis.xreadgroup(group, consumer, _streams, count=1)
        parsed_messages = []

        while stream_messages:
            for stream, messages in stream_messages:
                for msg in messages:
                    parsed_messages.append((stream, msg))

            stream_messages = self._redis.xreadgroup(group, consumer, _streams, count=1)

        return parsed_messages

    def init(self):
        group = "GROUP1"
        consumer = "MARKETPLACE"
        streams = self.router.routes.keys()

        for stream in streams:
            try:
                self._redis.xgroup_create(stream, group, mkstream=True)
            except Exception as e:
                print(e)

        return group, streams, consumer

    def listen(self) -> None:
        group, streams, consumer = self.init()

        try:
            self.handle_pending_messages(group, streams)
            messages = self.parse_messages(group, consumer, streams)

            for stream, msg in messages:
                self.handle_message(group, stream, msg)
        except Exception as e:
            print(e)


def test_run():
    print("start")
    while True:
        EventCatcher().listen()
        time.sleep(10)
