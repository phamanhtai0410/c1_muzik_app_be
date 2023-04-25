import json
from decimal import Decimal

import pytest

from src.activity.models import CollectionStat
from src.activity.services.top_collections import get_top_collections
from src.activity.tasks import update_collection_stat_info


@pytest.mark.django_db
def test_top_colections(
    mixer, token, active_user, second_user, follower, john_snow, currency
):
    second_token = mixer.blend(
        "store.Token", collection__standard="ERC1155", total_supply=10
    )
    boring_token = mixer.blend(
        "store.Token", collection__standard="ERC1155", total_supply=10
    )
    mixer.cycle(2).blend(
        "activity.TokenHistory",
        method="Buy",
        token=(token for token in [token, second_token]),
        old_owner=(seller for seller in [active_user, second_user]),
        new_owner=follower,
        price=(price for price in [100, 200]),
        currency=currency,
    )
    update_collection_stat_info()

    # check collection stat updating
    assert CollectionStat.objects.filter(collection=token.collection).exists()
    assert CollectionStat.objects.filter(collection=second_token.collection).exists()
    assert not CollectionStat.objects.filter(
        collection=boring_token.collection
    ).exists()

    # check usd price calculating
    assert CollectionStat.objects.get(collection=token.collection).amount == Decimal(
        100000.00
    )
    assert CollectionStat.objects.get(
        collection=second_token.collection
    ).amount == Decimal(200000.00)

    # check sorting
    top_collections = get_top_collections(None)
    assert top_collections[0]["url"] == second_token.collection.url
    assert top_collections[0]["amount"] == Decimal(200000.00)
    assert top_collections[1]["url"] == token.collection.url
    assert top_collections[1]["amount"] == Decimal(100000.00)

    # add auction which reverts top order and recheck all
    mixer.blend(
        "activity.TokenHistory",
        method="AuctionWin",
        token=token,
        old_owner=active_user,
        new_owner=follower,
        price=500,
        currency=currency,
    )
    update_collection_stat_info()

    # check collection stat updating
    assert CollectionStat.objects.filter(collection=token.collection).exists()
    assert CollectionStat.objects.filter(collection=second_token.collection).exists()
    assert not CollectionStat.objects.filter(
        collection=boring_token.collection
    ).exists()

    # check usd price calculating
    assert CollectionStat.objects.get(collection=token.collection).amount == Decimal(
        600000.00
    )
    assert CollectionStat.objects.get(
        collection=second_token.collection
    ).amount == Decimal(200000.00)

    # check sorting
    top_collections = get_top_collections(None)
    assert top_collections[0]["url"] == token.collection.url
    assert top_collections[0]["amount"] == Decimal(600000.00)
    assert top_collections[1]["url"] == second_token.collection.url
    assert top_collections[1]["amount"] == Decimal(200000.00)

    # check caching
    stat = CollectionStat.objects.get(collection__id=top_collections[0]["url"])
    stat.amount *= 2
    stat.save()
    top_collections_cached = get_top_collections(None)
    assert top_collections_cached[0]["amount"] == str(top_collections[0]["amount"])
