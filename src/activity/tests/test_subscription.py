import pytest

from src.activity.models import ActivitySubscription, UserAction


@pytest.mark.django_db
def test_token_history_subscription(
    mixer, token, active_user, second_user, follower, john_snow
):
    # create followings: users get incoming history, followers get outcoming history
    UserAction.objects.create(user=follower, whom_follow=second_user, method="follow")
    UserAction.objects.create(user=follower, whom_follow=active_user, method="follow")

    # check mint history (followers of minter get notifications)
    history = mixer.blend(
        "activity.TokenHistory",
        method="Mint",
        amount=10,
        old_owner=active_user,
        token=token,
    )
    assert ActivitySubscription.objects.filter(token_history=history).count() == 2
    assert not ActivitySubscription.objects.filter(
        method="Mint", type="self", token_history=history, receiver=active_user
    ).exists()
    assert ActivitySubscription.objects.filter(
        method="Mint", type="follow", token_history=history, receiver=follower
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="Mint", token_history=history, receiver=john_snow
    ).exists()

    # check listing history (followers of lister get notifications)
    history = mixer.blend(
        "activity.TokenHistory",
        method="Listing",
        amount=10,
        old_owner=active_user,
        token=token,
    )
    assert ActivitySubscription.objects.filter(token_history=history).count() == 2
    assert not ActivitySubscription.objects.filter(
        method="Listing", type="self", token_history=history, receiver=active_user
    ).exists()
    assert ActivitySubscription.objects.filter(
        method="Listing", type="follow", token_history=history, receiver=follower
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="Listing", type="self", token_history=history, receiver=follower
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="Listing", token_history=history, receiver=john_snow
    ).exists()

    # check transfer history (followers of sender get notification)
    history = mixer.blend(
        "activity.TokenHistory",
        method="Transfer",
        amount=10,
        old_owner=active_user,
        token=token,
        new_owner=second_user,
    )
    assert ActivitySubscription.objects.filter(token_history=history).count() == 2
    assert not ActivitySubscription.objects.filter(
        method="Transfer", type="self", token_history=history, receiver=active_user
    ).exists()
    assert ActivitySubscription.objects.filter(
        method="Transfer", type="follow", token_history=history, receiver=follower
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="Transfer", type="self", token_history=history, receiver=follower
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="Transfer", token_history=history, receiver=john_snow
    ).exists()

    # check buy history (followers of both seller and buyer get notification)
    history = mixer.blend(
        "activity.TokenHistory",
        method="Buy",
        amount=10,
        old_owner=active_user,
        token=token,
        new_owner=second_user,
    )
    assert ActivitySubscription.objects.filter(token_history=history).count() == 3
    assert ActivitySubscription.objects.filter(
        method="Buy", type="self", token_history=history, receiver=active_user
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="Buy", type="self", token_history=history, receiver=second_user
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="Buy",
        type="follow",
        token_history=history,
        receiver=follower,
        source=active_user,
    ).exists()
    assert ActivitySubscription.objects.filter(
        method="Buy",
        type="follow",
        token_history=history,
        receiver=follower,
        source=second_user,
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="Buy", type="self", token_history=history, receiver=follower
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="Buy", token_history=history, receiver=john_snow
    ).exists()

    # check auction win history (buyer get notification, so do his followers)
    history = mixer.blend(
        "activity.TokenHistory",
        method="AuctionWin",
        amount=1,
        old_owner=active_user,
        token=token,
        new_owner=second_user,
    )
    assert ActivitySubscription.objects.filter(token_history=history).count() == 2
    assert not ActivitySubscription.objects.filter(
        method="AuctionWin", type="self", token_history=history, receiver=active_user
    ).exists()
    assert ActivitySubscription.objects.filter(
        method="AuctionWin", type="both", token_history=history, receiver=second_user
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="AuctionWin",
        type="follow",
        token_history=history,
        receiver=follower,
        source=active_user,
    ).exists()
    assert ActivitySubscription.objects.filter(
        method="AuctionWin",
        type="follow",
        token_history=history,
        receiver=follower,
        source=second_user,
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="AuctionWin", type="self", token_history=history, receiver=follower
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="AuctionWin", token_history=history, receiver=john_snow
    ).exists()


@pytest.mark.django_db
def test_user_action_subscription(
    mixer, token, active_user, second_user, follower, john_snow
):
    # check followings: users get incoming history, followers get outcoming history
    UserAction.objects.create(user=follower, whom_follow=second_user, method="follow")
    follow_action = UserAction.objects.create(
        user=follower, whom_follow=active_user, method="follow"
    )

    assert (
        ActivitySubscription.objects.filter(
            method="follow", user_action=follow_action
        ).count()
        == 2
    )
    assert ActivitySubscription.objects.filter(
        method="follow", user_action=follow_action, receiver=active_user, type="self"
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="follow", user_action=follow_action, receiver=active_user, type="follow"
    ).exists()
    assert ActivitySubscription.objects.filter(
        method="follow", user_action=follow_action, receiver=follower, type="follow"
    ).exists()
    assert not ActivitySubscription.objects.filter(
        method="follow", user_action=follow_action, receiver=follower, type="self"
    ).exists()

    # check likes: user is notificated if other user (not self) liked token, followers get data about like sending
    like = UserAction.objects.create(user=second_user, token=token, method="like")
    assert ActivitySubscription.objects.filter(
        type="self", user_action=like, receiver=active_user
    ).exists()
    assert not ActivitySubscription.objects.filter(
        type="self", user_action=like, receiver=second_user
    ).exists()
    assert ActivitySubscription.objects.filter(
        type="follow", user_action=like, receiver=follower, source=second_user
    ).exists()
    assert not ActivitySubscription.objects.filter(
        type="follow", user_action=like, receiver=follower, source=active_user
    ).exists()
    assert not ActivitySubscription.objects.filter(
        type="self", user_action=like, receiver=follower
    ).exists()
    assert not ActivitySubscription.objects.filter(
        user_action=like, receiver=john_snow
    ).exists()

    self_like = UserAction.objects.create(user=active_user, token=token, method="like")
    assert not ActivitySubscription.objects.filter(
        type="self", user_action=self_like, receiver=active_user
    ).exists()
    assert not ActivitySubscription.objects.filter(
        type="follow", user_action=self_like, receiver=follower, source=active_user
    ).exists()
    assert not ActivitySubscription.objects.filter(
        type="self", user_action=self_like, receiver=follower
    ).exists()
    assert not ActivitySubscription.objects.filter(
        user_action=self_like, receiver=john_snow
    ).exists()


@pytest.mark.django_db
def test_bids_history_subscription(
    mixer, token, active_user, second_user, follower, john_snow, currency
):
    # set on sale
    ownership = token.ownerships.first()
    ownership.selling = True
    ownership.selling_quantity = 1
    ownership.minimal_bid = 10
    ownership.currency = currency
    ownership.save()

    UserAction.objects.create(user=follower, whom_follow=second_user, method="follow")
    UserAction.objects.create(user=follower, whom_follow=active_user, method="follow")
    history = mixer.blend("activity.BidsHistory", token=token, user=second_user)

    assert ActivitySubscription.objects.filter(
        type="self", bids_history=history, receiver=active_user
    ).exists()
    assert ActivitySubscription.objects.filter(
        type="follow", bids_history=history, receiver=follower, source=second_user
    ).exists()
    assert not ActivitySubscription.objects.filter(
        type="follow", bids_history=history, receiver=follower, source=active_user
    ).exists()
    assert not ActivitySubscription.objects.filter(
        type="self", bids_history=history, receiver=second_user
    ).exists()
    assert not ActivitySubscription.objects.filter(
        bids_history=history, receiver=john_snow
    ).exists()
