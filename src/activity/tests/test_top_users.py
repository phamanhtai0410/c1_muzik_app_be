from decimal import Decimal

import pytest

from src.activity.models import UserStat
from src.activity.services.top_users import get_top_users
from src.activity.tasks import update_top_users_info


@pytest.mark.django_db
def test_top_users(
    mixer, token, active_user, second_user, follower, john_snow, currency
):
    mixer.cycle(2).blend(
        "activity.TokenHistory",
        method="Buy",
        old_owner=(seller for seller in [active_user, second_user]),
        new_owner=follower,
        price=(price for price in [100, 200]),
        currency=currency,
    )
    update_top_users_info()

    # check user stat updating
    assert UserStat.objects.filter(user=active_user, network=None).exists()
    assert UserStat.objects.filter(user=second_user, network=None).exists()
    assert not UserStat.objects.filter(user=follower, network=None).exists()
    assert not UserStat.objects.filter(user=john_snow, network=None).exists()

    # check usd price calculating
    assert UserStat.objects.get(user=active_user, network=None).amount == Decimal(
        100000.00
    )
    assert UserStat.objects.get(user=second_user, network=None).amount == Decimal(
        200000.00
    )

    # check sorting
    top_users = get_top_users(None)
    assert top_users[0]["user"]["id"] == second_user.id
    assert top_users[0]["amount"] == "200000.00"
    assert top_users[1]["user"]["id"] == active_user.id
    assert top_users[1]["amount"] == "100000.00"

    # add auction which reverts top order and recheck all
    mixer.blend(
        "activity.TokenHistory",
        method="AuctionWin",
        old_owner=active_user,
        new_owner=follower,
        price=500,
        currency=currency,
    )
    update_top_users_info()

    # check user stat updating
    assert UserStat.objects.filter(user=active_user, network=None).exists()
    assert UserStat.objects.filter(user=second_user, network=None).exists()
    assert not UserStat.objects.filter(user=follower, network=None).exists()
    assert not UserStat.objects.filter(user=john_snow, network=None).exists()

    # check usd price calculating
    assert UserStat.objects.get(user=active_user, network=None).amount == Decimal(
        600000.00
    )
    assert UserStat.objects.get(user=second_user, network=None).amount == Decimal(
        200000.00
    )

    # check sorting
    top_users = get_top_users(None)
    assert top_users[0]["user"]["id"] == active_user.id
    assert top_users[0]["amount"] == "600000.00"
    assert top_users[1]["user"]["id"] == second_user.id
    assert top_users[1]["amount"] == "200000.00"

    # check caching
    stat = UserStat.objects.get(user__id=top_users[0]["user"]["id"], network=None)
    stat.amount *= 2
    stat.save()
    top_users_cached = get_top_users(None)
    assert top_users_cached[0]["amount"] == str(top_users[0]["amount"])
