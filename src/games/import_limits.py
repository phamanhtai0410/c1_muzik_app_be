from src.networks.models import Network
from src.utilities import RedisClient


def increment_import_requests(network: Network, amount: int = 1):
    redis = RedisClient()
    redis_key = f"import_requests__{network.name}"
    redis.connection.incrby(redis_key, str(amount))


def get_import_requests_exceeded(network: Network):
    redis = RedisClient()
    redis_key = f"import_requests__{network.name}"
    current_value = redis.connection.get(redis_key) or 0

    if network.daily_import_requests and int(current_value) >= (
        network.daily_import_requests
    ):
        return True
    else:
        return False
