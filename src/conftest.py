import pytest
from mixer.backend.django import mixer as _mixer

from src.tests.api_client import Client


@pytest.fixture
def mixer():
    return _mixer


@pytest.fixture
def api():
    return Client()


@pytest.fixture
def auth_api():
    return Client(is_authenticated=True)
