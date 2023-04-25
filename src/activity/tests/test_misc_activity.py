from decimal import Decimal

import pytest

from src.activity.models import ActivitySubscription
from src.activity.serializers import ActivitySerializer


@pytest.mark.django_db
def test_calculate_usd_price(
    mixer, token, active_user, second_user, follower, john_snow, currency
):
    history = mixer.blend(
        "activity.TokenHistory",
        method="Buy",
        old_owner=active_user,
        new_owner=second_user,
        price=200,
        currency=currency,
    )
    assert history.USD_price == Decimal(200000.00)


@pytest.mark.django_db
def test_serializer(mixer, token, active_user, second_user, follower, john_snow):
    # check UserAction
    mixer.blend(
        "activity.UserAction", user=follower, whom_follow=second_user, method="follow"
    )
    subscription = ActivitySubscription.objects.last()
    data = ActivitySerializer(subscription).data
    assert data["token_id"] is None  # no token in follow
    assert data["token_image"] is None
    assert data["token_name"] is None
    assert data["currency"] is None
    assert data["amount"] is None
    assert data["price"] == ""  # TODO fix to None? WTF?
    assert data["from_id"] == follower.url
    assert data["from_image"] == follower.avatar
    assert data["from_address"] == follower.username
    assert data["from_name"] == follower.get_name()
    assert data["to_id"] == second_user.url
    assert data["to_image"] == second_user.avatar
    assert data["to_address"] == second_user.username
    assert data["to_name"] == second_user.get_name()

    # check TokenHistory
    history = mixer.blend(
        "activity.TokenHistory",
        method="Buy",
        amount=10,
        old_owner=active_user,
        token=token,
        new_owner=second_user,
    )
    subscription = ActivitySubscription.objects.last()
    data = ActivitySerializer(subscription).data
    assert data["token_id"] == token.id
    assert data["token_image"] == token.image
    assert data["token_name"] == token.name
    assert data["currency"] == history.currency
    assert data["amount"] == history.amount
    assert data["price"] == history.price
    assert data["from_id"] == active_user.url
    assert data["from_image"] == active_user.avatar
    assert data["from_address"] == active_user.username
    assert data["from_name"] == active_user.get_name()
    assert data["to_id"] == second_user.url
    assert data["to_image"] == second_user.avatar
    assert data["to_address"] == second_user.username
    assert data["to_name"] == second_user.get_name()

    # check BidsHistory
    history = mixer.blend("activity.BidsHistory", token=token, user=active_user)
    subscription = ActivitySubscription.objects.last()
    data = ActivitySerializer(subscription).data
    assert data["token_id"] == token.id
    assert data["token_image"] == token.image
    assert data["token_name"] == token.name
    assert data["currency"] == history.currency
    assert data["amount"] is None  # bids only for 1155
    assert data["price"] == history.price
    assert data["from_id"] == active_user.url
    assert data["from_image"] == active_user.avatar
    assert data["from_address"] == active_user.username
    assert data["from_name"] == active_user.get_name()
    assert data["to_id"] is None  # only one user
    assert data["to_image"] is None
    assert data["to_address"] is None
    assert data["to_name"] is None
