import json

from django.db.models import Sum

from src.accounts.models import AdvUser
from src.activity.models import TokenHistory, UserStat
from src.activity.serializers import UserStatSerializer
from src.settings import config
from src.support.models import Config
from src.utilities import RedisClient


def update_users_stat(network):
    """
    Get all users with active sells at given period.
    Calculate sum of their "Selling" histories in USD
    """
    start_time, _ = Config.get_top_users_period()

    users = AdvUser.objects.filter(
        old_owner__method__in=["Buy", "AuctionWin"], old_owner__date__gte=start_time
    ).distinct()
    for user in users:
        user_stat, _ = UserStat.objects.get_or_create(network=network, user=user)
        filter_data = {
            "token__deleted": False,
            "date__gte": start_time,
            "method__in": ["Buy", "AuctionWin"],
            "old_owner": user,
        }
        if network:
            filter_data["currency__network"] = network
        user_stat.amount = TokenHistory.objects.filter(**filter_data).aggregate(
            sum_price=Sum("USD_price")
        )["sum_price"]
        user_stat.save()

    # Delete rows for users, which was not picked up in first filter
    UserStat.objects.exclude(user__in=users).delete()

    # delete all cached values after data update
    redis = RedisClient()
    redis_key_filter = "top_users__*"
    keys = redis.connection.keys(redis_key_filter)
    for key in keys:
        redis.connection.delete(key)


def get_top_users(network):
    _, days = Config.get_top_users_period()

    # try to get cached value if exists
    redis = RedisClient()
    redis_key = f"top_users__{days}"
    redis_key += f"__{network}" if network else ""
    data = redis.connection.get(redis_key)
    if data:
        return json.loads(data)

    # get sorted sellers list
    user_stats = UserStat.objects.all()
    if network:
        user_stats = user_stats.filter(network=network)
    else:
        user_stats = user_stats.filter(network__isnull=True)
    user_stats = user_stats.order_by("-amount")
    data = UserStatSerializer(user_stats[:10], many=True).data
    # cache result
    redis.connection.set(
        redis_key,
        json.dumps(data, ensure_ascii=False, default=str),
        ex=config.REDIS_EXPIRATION_TIME,
    )
    return data
