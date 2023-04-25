from typing import TYPE_CHECKING

from src.rates.exceptions import CurrencyNotFound
from src.rates.models import UsdRate

if TYPE_CHECKING:
    from src.networks.models import Network


def get_currency_by_symbol(symbol: str, network: "Network" = None) -> "UsdRate":
    try:
        return UsdRate.objects.get(
            symbol=symbol,
            network=network,
        )
    except UsdRate.DoesNotExist:
        raise CurrencyNotFound
