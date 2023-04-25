import os

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from web3.auto import w3

from src.activity.models import UserAction
from src.store.models import Status


@pytest.mark.django_db
def test_login(api):
    """
    check login workflow
    """
    acc = Account.create()
    # invalid credentials
    response = api.post(
        "/api/v1/account/metamask_login/",
        data={"address": acc.address, "signed_msg": "admin"},
    )
    assert response.status_code == 404
    api.get(f"/api/v1/account/get_metamask_message/{acc.address}/")
    response = api.post(
        "/api/v1/account/metamask_login/",
        data={"address": acc.address, "signed_msg": "admin"},
    )
    assert response.status_code == 400

    # valid workflow
    msg = api.get(f"/api/v1/account/get_metamask_message/{acc.address}/")
    message = encode_defunct(text=msg.json())
    signed_message = w3.eth.account.sign_message(message, private_key=acc.key.hex())

    response = api.post(
        "/api/v1/account/metamask_login/",
        data={"address": acc.address, "signed_msg": signed_message.signature.hex()},
    )
    assert response.status_code == 200
    assert isinstance(response.json().get("token"), str)
    api.credentials(HTTP_AUTHORIZATION=f'Token {response.json().get("token")}')
    response = api.get("/api/v1/account/self/")
    assert response.status_code == 200

    # check credentials are valid only once
    response = api.post(
        "/api/v1/account/metamask_login/",
        data={"address": acc.address, "signed_msg": signed_message.signature.hex()},
    )
    assert response.status_code == 404
    api.get(f"/api/v1/account/get_metamask_message/{acc.address}/")
    response = api.post(
        "/api/v1/account/metamask_login/",
        data={"address": acc.address, "signed_msg": signed_message.signature.hex()},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_self_view_get(api, auth_api):
    URL = "/api/v1/account/self/"
    response = auth_api.get(URL)
    assert response.status_code == 200
    assert response.json().get("display_name") == "Rodion"

    response = api.get(URL)
    assert response.status_code == 401


@pytest.mark.skipif(
    not os.getenv("USE_WS"), reason="Websockets are disabled"
)  # TODO pass envs to tets.yml
@pytest.mark.django_db
def test_get_ws_token(api, auth_api):
    URL = "/api/v1/account/self/get_ws_token/"
    response = auth_api.get(URL)
    assert response.status_code == 200
    assert (response.json(), str)

    response = api.get(URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_self_view_patch(api, auth_api):
    URL = "/api/v1/account/self/"
    response = auth_api.patch(URL, data={"display_name": "Kubernetes"})
    assert response.status_code == 200
    assert response.json().get("display_name") == "Kubernetes"

    response = auth_api.patch(URL, data={"display_name": "not valid length" * 20})
    assert response.status_code == 400

    response = api.patch(URL, data={"display_name": "Kubernetes"})
    assert response.status_code == 401


@pytest.mark.django_db
def test_get_other_view(mixer, api):
    URL = "/api/v1/account/{user}/"
    user = mixer.blend("accounts.AdvUser", custom_url="other_man")

    response = api.get(URL.format(user=user.id))
    assert response.status_code == 200
    assert response.json().get("url") == user.custom_url

    response = api.get(URL.format(user=user.custom_url))
    assert response.status_code == 200
    assert response.json().get("url") == user.custom_url

    response = api.get(URL.format(user="non-exists-user"))
    assert response.status_code == 404


@pytest.mark.django_db
def test_follow_view(mixer, api, auth_api):
    URL = "/api/v1/account/self/follow/"
    user = mixer.blend("accounts.AdvUser", custom_url="follower")

    assert not UserAction.objects.filter(user=auth_api.user, whom_follow=user).exists()
    response = auth_api.post(URL, data={"id": user.id})
    assert response.status_code == 200
    assert UserAction.objects.filter(user=auth_api.user, whom_follow=user).exists()

    response = auth_api.post(URL, data={"id": auth_api.user.id})
    assert response.status_code == 400

    response = api.post(URL, data={"id": 99})
    assert response.status_code == 401


@pytest.mark.django_db
def test_unfollow_view(mixer, api, auth_api):
    URL = "/api/v1/account/self/unfollow/"
    user = mixer.blend("accounts.AdvUser", custom_url="unfollower")
    mixer.blend("activity.UserAction", user=auth_api.user, whom_follow=user)

    response = auth_api.post(URL, data={"id": user.id})
    assert response.status_code == 200
    assert not UserAction.objects.filter(user=auth_api.user, whom_follow=user).exists()

    response = auth_api.post(URL, data={"id": user.id})
    assert response.status_code == 200

    response = api.post(URL, data={"id": 99})
    assert response.status_code == 401


@pytest.mark.django_db
def test_like_view(mixer, api, auth_api):
    URL = "/api/v1/account/self/like/"
    token = mixer.blend("store.Token", status=Status.COMMITTED)

    response = auth_api.post(URL, data={"id": token.id})
    assert response.status_code == 200
    assert UserAction.objects.filter(
        user=auth_api.user,
        whom_follow=None,
        method="like",
        token=token,
    ).exists()

    response = auth_api.post(URL, data={"id": token.id})
    assert response.status_code == 200
    assert not UserAction.objects.filter(
        user=auth_api.user,
        whom_follow=None,
        method="like",
        token=token,
    ).exists()

    response = api.post(URL, data={"id": 99})
    assert response.status_code == 401

    response = auth_api.post(URL, data={"id": 0})
    assert response.status_code == 404


@pytest.mark.django_db
def test_get_user_collections_view(mixer, api, auth_api):
    URL = "/api/v1/account/self/collections/"
    col_eth, col_polygon = mixer.cycle(2).blend(
        "store.Collection",
        status=Status.COMMITTED,
        creator=auth_api.user,
        network__name=(network for network in ("Ethereum", "Polygon")),
    )
    mixer.blend(
        "store.Collection",
        status=Status.PENDING,
        creator=auth_api.user,
        network__name="Ethereum",
    )

    response = auth_api.get(URL)
    assert response.status_code == 200
    assert [col["url"] for col in response.json().get("results")] == [
        col_eth.url,
        col_polygon.url,
    ]

    response = auth_api.get(URL, data={"network": "Ethereum"})
    assert response.status_code == 200
    assert len(response.json().get("results")) == 1
    assert response.json().get("results")[0]["url"] == col_eth.url

    response = api.get(URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_following_view(mixer, api):
    URL = "/api/v1/account/{user}/following/"
    user = mixer.blend("accounts.AdvUser")
    followers = mixer.cycle(2).blend("accounts.AdvUser")
    followings = mixer.cycle(3).blend("accounts.AdvUser")
    mixer.cycle(3).blend(
        "activity.UserAction",
        user=user,
        method="follow",
        whom_follow=(us for us in followings),
    )
    mixer.cycle(2).blend(
        "activity.UserAction",
        whom_follow=user,
        method="follow",
        user=(us for us in followers),
    )

    response = api.get(URL.format(user=user.id))
    assert response.status_code == 200
    assert len(response.json().get("results")) == 3

    response = api.get(URL.format(user=0))
    assert response.status_code == 404


@pytest.mark.django_db
def test_followers_view(mixer, api):
    URL = "/api/v1/account/{user}/followers/"
    user = mixer.blend("accounts.AdvUser")
    followers = mixer.cycle(3).blend("accounts.AdvUser")
    following = mixer.blend("accounts.AdvUser")
    mixer.cycle(3).blend(
        "activity.UserAction",
        whom_follow=user,
        method="follow",
        user=(us for us in followers),
    )
    mixer.blend(
        "activity.UserAction", user=user, method="follow", whom_follow=following
    )
    response = api.get(URL.format(user=user.id))
    assert response.status_code == 200
    assert len(response.json().get("results")) == 3

    response = api.get(URL.format(user=0))
    assert response.status_code == 404
