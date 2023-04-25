import logging

from django.db import transaction

from scanners.base import HandlerABC
from src.store.models import Token
from src.support.models import Config


class HandlerApproval(HandlerABC):
    TYPE = "approval"
    TIMEOUT = Config.object().approval_timeout if Config.object() else None

    @transaction.atomic
    def save_event(self, event_data):
        data = self.scanner.parse_data_approval(event_data)
        self.logger.debug(f"New event: {data}")
        # only if approve is revoked from exchange
        user = self.get_owner(data.account)
        if (
            not data.is_approved
            and data.operator == self.network.exchange_address.lower()
        ):
            # remove from sale all token salse by account
            tokens = Token.objects.filter(
                ownerships__owner=user,
                ownerships__selling=True,
                collection__address__iexact=self.contract.address,
            ).distinct()
            for token in tokens:
                errors = token.controller.change_sell_status(user=user)
                if errors:
                    logging.error("errors")
            logging.info(f"all {user.username}'s tokens have been removed from sale")
