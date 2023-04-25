from django.db import transaction

from scanners.base import HandlerABC
from src.activity.models import TokenHistory
from src.store.models import Collection, Status


class HandlerDeploy(HandlerABC):
    TYPE = "deploy"

    @transaction.atomic
    def save_event(self, event_data):
        data = self.scanner.parse_data_deploy(event_data)
        self.logger.debug(f"New event: {data}")

        if TokenHistory.objects.filter(tx_hash=data.tx_hash).exists():
            self.logger.debug(f"History with tx hash {data.tx_hash} exists")
            return

        collection = Collection.objects.filter(
            name__iexact=data.collection_name,
            network=self.network,
        )
        if collection.exists():
            collection.update(
                status=Status.COMMITTED,
                deploy_block=data.deploy_block,
                address=data.address,
            )
