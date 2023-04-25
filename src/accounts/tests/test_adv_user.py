import pytest
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import ErrorDetail

from src.accounts.models import AdvUser
from src.accounts.serializers import PatchSerializer, UserSerializer
from src.activity.models import UserAction
from src.settings import config


@pytest.mark.django_db
def test_adv_user_manager(mixer):
    """
    test AdvUser manager (get_by_custom_url) with url field changing
    """
    with pytest.raises(ObjectDoesNotExist):
        AdvUser.objects.get_by_custom_url("testurl")

    adv_user = mixer.blend("accounts.AdvUser", display_name="testuser")
    assert adv_user.url == adv_user.id
    adv_user.custom_url = "testurl"
    adv_user.save()

    config.USER_URL_FIELD = "custom_url"
    assert adv_user.url == adv_user.custom_url
    assert (
        AdvUser.objects.get_by_custom_url(adv_user.id).display_name
        == adv_user.display_name
    )
    assert (
        AdvUser.objects.get_by_custom_url(str(adv_user.id)).display_name
        == adv_user.display_name
    )
    assert (
        AdvUser.objects.get_by_custom_url(adv_user.url).display_name
        == adv_user.display_name
    )

    config.USER_URL_FIELD = "display_name"
    assert adv_user.url == adv_user.display_name
    assert (
        AdvUser.objects.get_by_custom_url(adv_user.url).display_name
        == adv_user.display_name
    )
    with pytest.raises(ObjectDoesNotExist):
        AdvUser.objects.get_by_custom_url(adv_user.custom_url)

    # change config back cause other tests may use it
    config.USER_URL_FIELD = "custom_url"


@pytest.mark.django_db
def test_default_avatar(mixer):
    """
    test automatic default_avatar setting
    """
    user = mixer.blend("accounts.AdvUser")
    assert user.avatar_ipfs is None
    avatar = mixer.blend("accounts.DefaultAvatar", image="image")
    assert avatar.image == "image"
    user = mixer.blend("accounts.AdvUser")
    assert user.avatar_ipfs == avatar.image
    user.avatar_ipfs = "image2"
    user.save()
    assert user.avatar_ipfs == "image2"


@pytest.mark.parametrize(
    ["patch_data", "expected_results"],
    [
        (
            {
                "display_name": "Rodion",
                "custom_url": "rodi",
                "bio": "lorem ipsum",
                "twitter": "rodion",
                "instagram": "rodion",
                "facebook": "rodion",
                "site": "rodion.com",
                "cover_ipfs": "cover_ipfs",
                "avatar_ipfs": "avatar_ipfs",
                "email": "rodion@mail.ru",
            },
            "Rodion",
        ),  # base logic (valid)
        (
            {
                "display_name": "occupied_display_name",
                "custom_url": "rodi",
                "bio": "lorem ipsum",
                "twitter": "rodion",
                "instagram": "rodion",
                "facebook": "rodion",
                "site": "rodion.com",
                "cover_ipfs": "cover_ipfs",
                "avatar_ipfs": "avatar_ipfs",
                "email": "rodion@mail.ru",
            },
            {"display_name": "this display_name is occupied"},
        ),  # occupied display name
        (
            {
                "display_name": "Rodion",
                "custom_url": "occupied_custom_url",
                "bio": "lorem ipsum",
                "twitter": "rodion",
                "instagram": "rodion",
                "facebook": "rodion",
                "site": "rodion.com",
                "cover_ipfs": "cover_ipfs",
                "avatar_ipfs": "avatar_ipfs",
                "email": "rodion@mail.ru",
            },
            {
                "custom_url": [
                    ErrorDetail(
                        string="user with this custom url already exists.",
                        code="unique",
                    )
                ]
            },
        ),  # occupied custom url TODO fix the error?
        (
            {
                "display_name": "Rodion",
                "custom_url": "rodi",
                "bio": "occupied_bio",
                "twitter": "rodion",
                "instagram": "rodion",
                "facebook": "rodion",
                "site": "rodion.com",
                "cover_ipfs": "cover_ipfs",
                "avatar_ipfs": "avatar_ipfs",
                "email": "rodion@mail.ru",
            },
            "Rodion",
        ),  # occupied bio (valid)
        (
            {
                "display_name": "Rodion",
                "custom_url": "rodi",
                "bio": "lorem ipsum",
                "twitter": "occupied_twitter",
                "instagram": "rodion",
                "facebook": "rodion",
                "site": "rodion.com",
                "cover_ipfs": "cover_ipfs",
                "avatar_ipfs": "avatar_ipfs",
                "email": "rodion@mail.ru",
            },
            {"twitter": "this twitter is occupied"},
        ),  # occupied twitter
        (
            {
                "display_name": "Rodion",
                "custom_url": "rodi",
                "bio": "lorem ipsum",
                "twitter": "rodion",
                "instagram": "occupied_instagram",
                "facebook": "rodion",
                "site": "rodion.com",
                "cover_ipfs": "cover_ipfs",
                "avatar_ipfs": "avatar_ipfs",
                "email": "rodion@mail.ru",
            },
            {"instagram": "this instagram is occupied"},
        ),  # occupied instagram
        (
            {
                "display_name": "Rodion",
                "custom_url": "rodi",
                "bio": "lorem ipsum",
                "twitter": "rodion",
                "instagram": "rodion",
                "facebook": "occupied_facebook",
                "site": "rodion.com",
                "cover_ipfs": "cover_ipfs",
                "avatar_ipfs": "avatar_ipfs",
                "email": "rodion@mail.ru",
            },
            {"facebook": "this facebook is occupied"},
        ),  # occupied facebook
        (
            {
                "display_name": "Rodion",
                "custom_url": "rodi",
                "bio": "lorem ipsum",
                "twitter": "rodion",
                "instagram": "rodion",
                "facebook": "rodion",
                "site": "occupied_site.ru",
                "cover_ipfs": "cover_ipfs",
                "avatar_ipfs": "avatar_ipfs",
                "email": "rodion@mail.ru",
            },
            {"site": "this site is occupied"},
        ),  # occupied site
        (
            {
                "display_name": "Rodion",
                "custom_url": "rodi",
                "bio": "lorem ipsum",
                "twitter": "rodion",
                "instagram": "rodion",
                "facebook": "rodion",
                "site": "rodion.com",
                "cover_ipfs": "occupied_cover",
                "avatar_ipfs": "avatar_ipfs",
                "email": "rodion@mail.ru",
            },
            "Rodion",
        ),  # occupied cover (valid)
        (
            {
                "display_name": "Rodion",
                "custom_url": "rodi",
                "bio": "lorem ipsum",
                "twitter": "rodion",
                "instagram": "rodion",
                "facebook": "rodion",
                "site": "rodion.com",
                "cover_ipfs": "cover_ipfs",
                "avatar_ipfs": "occupied_avatar",
                "email": "rodion@mail.ru",
            },
            "Rodion",
        ),  # occupied avatar (valid)
        (
            {
                "display_name": "Rodion",
                "custom_url": "rodi",
                "bio": "lorem ipsum",
                "twitter": "rodion",
                "instagram": "rodion",
                "facebook": "rodion",
                "site": "rodion.com",
                "cover_ipfs": "cover_ipfs",
                "avatar_ipfs": "avatar_ipfs",
                "email": "occupied_email@gmail.com",
            },
            {"email": "this email is occupied"},
        ),  # occupied email
        (
            {
                "display_name": "Rodion",
                "custom_url": "111",
                "bio": "lorem ipsum",
                "twitter": "rodion",
                "instagram": "rodion",
                "facebook": "rodion",
                "site": "rodion.com",
                "cover_ipfs": "cover_ipfs",
                "avatar_ipfs": "avatar_ipfs",
                "email": "rodion@mail.ru",
            },
            {"custom_url": f"can't contain only digits"},
        ),  # forbidden digit custom url
        ({"display_name": "Rodion"}, "Rodion"),  # check partial allowed
    ],
)
@pytest.mark.django_db
def test_user_patch_serializer(mixer, patch_data, expected_results):
    """
    test AdvUser patch serializer by mixing valid and invalid (occupied/forbidden) data
    """
    # blend user for checking occupied data
    mixer.blend(
        "accounts.AdvUser",
        display_name="occupied_display_name",
        custom_url="occupied_custom_url",
        bio="occupied_bio",
        twitter="occupied_twitter",
        instagram="occupied_instagram",
        facebook="occupied_facebook",
        site="occupied_site.ru",
        cover_ipfs="occupied_cover",
        avatar_ipfs="occupied_avatar",
        email="occupied_email@gmail.com",
    )

    # blend active user, patch him
    user = mixer.blend("accounts.AdvUser")
    serializer = PatchSerializer(user, data=patch_data, partial=True)

    # asserts
    if serializer.is_valid():
        result = serializer.save()
        if isinstance(result, dict):
            assert result == expected_results
        else:
            assert result.display_name == expected_results
    if serializer.errors:
        assert serializer.errors == expected_results


@pytest.mark.django_db
def test_user_serializer(mixer):
    """
    check user serializer
    """
    follower = mixer.blend("accounts.AdvUser", display_name="follower")
    following = mixer.blend("accounts.AdvUser", display_name="following")
    user = mixer.blend(
        "accounts.AdvUser", username="user", display_name="name", custom_url="url"
    )
    UserAction.objects.create(method="follow", user=user, whom_follow=following)
    UserAction.objects.create(method="follow", user=follower, whom_follow=user)

    data = UserSerializer(user, context={"user": follower}).data
    # check data
    assert data["address"] == "user"
    assert data["name"] == "name"
    assert data["url"] == "url"

    # check serializer method fields
    assert data["follows"][0]["display_name"] == "following"
    assert data["follows_count"] == 1
    assert data["followers"][0]["display_name"] == "follower"
    assert data["followers_count"] == 1
    assert data["is_following"] is True

    data = UserSerializer(user, context={"user": following}).data
    assert data["is_following"] is False
