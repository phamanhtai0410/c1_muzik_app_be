class Router:
    def __init__(self):
        self.routes = {}

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(Router, cls).__new__(cls)
        return cls.instance

    def register(self, event_name):
        print(f"register: {event_name}")

        def _(func):
            self.routes[event_name] = func
            return func

        return _


def get_router():
    return Router()
