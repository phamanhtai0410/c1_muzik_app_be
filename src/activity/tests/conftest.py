import pytest


@pytest.fixture
def token(mixer):
    # create initial token instance
    return mixer.blend("store.Token", collection__standard="ERC1155", total_supply=10)


@pytest.fixture
def active_user(mixer, token):
    # Active user who owns token
    active_user = mixer.blend("accounts.AdvUser")
    mixer.blend("store.Ownership", token=token, owner=active_user, quantity=10)
    token.owners.add(active_user)
    return active_user


@pytest.fixture
def john_snow(mixer):
    # John Snow knows nothing
    return mixer.blend("accounts.AdvUser")


@pytest.fixture
def second_user(mixer):
    # second active user
    return mixer.blend("accounts.AdvUser")


@pytest.fixture
def follower(mixer):
    # mainly for testing follower notifications or some mundane jobs
    return mixer.blend("accounts.AdvUser")


@pytest.fixture
def currency(mixer):
    return mixer.blend("rates.UsdRate", rate=1000, decimals=18)
