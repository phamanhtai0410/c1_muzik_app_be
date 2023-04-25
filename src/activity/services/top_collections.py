import json
from datetime import date, timedelta

from django.db.models import Avg, Count, F, Sum

from src.activity.models import CollectionStat, TokenHistory
from src.activity.serializers import (
    CollectionStatsSerializer,
    CollectionTradeDataSerializer,
)
from src.settings import config
from src.store.models import Collection
from src.store.serializers import TopCollectionsSerializer
from src.support.models import Config
from src.utilities import RedisClient


def update_collection_stat():
    filter_day = date.today()
    token_history = TokenHistory.objects.filter(
        token__deleted=False,
        date__year=filter_day.year,
        date__month=filter_day.month,
        date__day=filter_day.day,
        method__in=["Buy", "AuctionWin"],
        token__collection__is_default=False,
    )
    result = (
        token_history.annotate(
            price_=F("USD_price"),
            collection=F("token__collection"),
            price_single=F("USD_price") / F("amount"),
        )
        .values("collection")
        .annotate(price=Sum("price_"))
        .annotate(trade_count=Count("id"))
        .annotate(average_price=Avg("price_single"))
    )
    for data in result:
        collection = Collection.objects.filter(id=data.get("collection")).first()
        if not collection:
            continue
        collection_stat, _ = CollectionStat.objects.get_or_create(
            collection=collection,
            date=filter_day,
        )
        collection_stat.amount = data.get("price")
        collection_stat.average_price = data.get("average_price")
        collection_stat.number_of_trades = data.get("trade_count")
        collection_stat.save()

    # delete all cached values after data update
    redis = RedisClient()
    for redis_key_filter in ["top_collection__*", "chart__*", "trade_data__*"]:
        keys = redis.connection.keys(redis_key_filter)
        for key in keys:
            redis.connection.delete(key)


def get_top_collections(network):
    start_date, period = Config.get_top_collections_period()
    end_date = date.today()

    # try to get cached value if exists
    redis = RedisClient()
    redis_key = f"top_collection__{period}__{end_date}"
    redis_key += f"__{network}" if network else ""

    data = redis.connection.get(redis_key)
    if data:
        return json.loads(data)

    # get sorted list of all collection stats and serialize
    collections = (
        Collection.objects.committed().network(network).filter(is_default=False)
    )
    data = TopCollectionsSerializer(
        collections, many=True, context={"start_date": start_date, "end_date": end_date}
    ).data
    data = sorted(data, key=lambda x: x.get("amount") or 0, reverse=True)

    # cache result
    redis.connection.set(
        redis_key,
        json.dumps(data, ensure_ascii=False, default=str),
        ex=config.REDIS_EXPIRATION_TIME,
    )

    return data


def get_collection_charts(collection, days):
    # try to get cached value if exists
    redis = RedisClient()
    redis_key = f"chart__{collection.name}__{days}"

    data = redis.connection.get(redis_key)
    if data:
        return json.loads(data)

    # get sorted list of all collection stats and serialize
    collection_stats = CollectionStat.objects.filter(collection=collection)
    if days and days != "all":
        start_date = date.today() - timedelta(days=int(days))
        collection_stats = collection_stats.filter(date__gte=start_date)
    collection_stats = collection_stats.order_by("date")
    data = CollectionStatsSerializer(collection_stats, many=True).data
    # cache result
    redis.connection.set(
        redis_key,
        json.dumps(data, ensure_ascii=False, default=str),
        ex=config.REDIS_EXPIRATION_TIME,
    )
    return data


def get_collection_trade_data(collection, days):
    # try to get cached value if exists
    redis = RedisClient()
    redis_key = f"trade_data__{collection.name}__{days}"

    data = redis.connection.get(redis_key)
    if data:
        return json.loads(data)

    filter_condition = {}
    if days and days != "all":
        start_date = date.today() - timedelta(days=int(days))
        filter_condition["date__gte"] = start_date

    collection.avg_price = collection.stats.filter(**filter_condition).aggregate(
        avg_price=Sum("average_price") / Sum("number_of_trades")
    )["avg_price"]
    collection.volume = collection.stats.filter(**filter_condition).aggregate(
        volume=Sum("amount")
    )["volume"]

    data = CollectionTradeDataSerializer(collection).data
    # cache result
    redis.connection.set(
        redis_key,
        json.dumps(data, ensure_ascii=False, default=str),
        ex=config.REDIS_EXPIRATION_TIME,
    )
    return data
