import logging

from celery import shared_task
from src.activity.services.top_collections import update_collection_stat
from src.activity.services.top_users import update_users_stat
from src.networks.models import Network

logger = logging.getLogger("celery")


@shared_task(name="update_top_users_info")
def update_top_users_info():
    logger.info("Start update top users info")
    # update info fot all networks separately and overall (with network = None)
    networks = list(Network.objects.all())
    networks.append(None)
    for network in networks:
        update_users_stat(network)


@shared_task(name="update_collection_stat_info")
def update_collection_stat_info():
    update_collection_stat()
