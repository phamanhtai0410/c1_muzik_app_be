import pytest

from src.rates.models import UsdRate
from src.rates.tasks import rates_checker


@pytest.mark.django_db
def test_rates_checker(mixer):
    """
    checks that valid currencies are processed successfully while invalid don't break the task
    """
    mixer.cycle(2).blend(
        "rates.UsdRate", coin_node=(coin_node for coin_node in ["invalid", "ethereum"])
    )
    rates_checker()
    assert UsdRate.objects.get(coin_node="ethereum").rate
    assert not UsdRate.objects.get(coin_node="invalid").rate
