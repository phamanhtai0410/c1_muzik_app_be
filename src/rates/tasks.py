import logging
import sys
import traceback

import requests

from celery import shared_task
from src.rates.models import UsdRate
from src.settings import config
from src.utilities import alert_bot

QUERY_FSYM = "usd"
logger = logging.getLogger("celery")


def get_rate(coin_code):
    res = requests.get(config.API_URL.format(coin_code=coin_code))
    if res.status_code != 200:
        raise Exception("cannot get exchange rate for {}".format(QUERY_FSYM))
    response = res.json()
    return response["market_data"]["current_price"][QUERY_FSYM]


@shared_task(name="rates_checker")
@alert_bot
def rates_checker():
    logger.info("celery is working")
    coin_nodes = UsdRate.objects.all().values_list("coin_node", flat=True)
    for coin_node in coin_nodes:
        try:
            rate = get_rate(coin_node)
        except Exception:
            logger.error("\n".join(traceback.format_exception(*sys.exc_info())))
            continue
        rates = UsdRate.objects.filter(coin_node=coin_node)
        rates.update(rate=rate)
