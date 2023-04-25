from src.support.exceptions import RoyaltyMaxValueException
from src.support.models import Config


def royalty_max_value_validator(value):
    if Config.object and value > Config.object().max_royalty_percentage:
        raise RoyaltyMaxValueException
