from datetime import timedelta

from django.db import transaction

from scanners.base import HandlerABC
from src.promotion.models import Promotion, PromotionOptions
from src.store.models import Token
from src.promotion.tasks import promotion_checker


class HandlerPromotion(HandlerABC):
    TYPE = "promotion"

    @transaction.atomic
    def save_event(self, event_data):
        data = self.scanner.parse_data_promotion(event_data)
        token = Token.objects.filter(
            internal_id=data.token_id,
            collection__address=data.collection_address,
            collection__network__chain_id=data.chain_id,
        ).first()
        self.logger.debug(f"New event: {data}")

        if not token:
            self.logger.warning(
                f"Token not found. Network: {self.network}, address: {data.collection_address}, internal id: {data.token_id}"
            )
            return
        owner = self.get_owner(data.buyer)
        if owner not in token.owners.all():
            self.logger.warning(f"User {owner.username} is not owner of the token")
            return
        ownership = token.ownerships.get(owner=owner)
        plan = PromotionOptions.objects.filter(package=data.package).first()
        if not plan:
            self.logger.warning(f"Plan not found not package {data.package}")
            return
        promotion = Promotion.objects.create(
            token=token,
            owner=ownership,
            status=Promotion.PromotionStatus.WAITING,
            duration=timedelta(days=plan.days),
            network=plan.promotion.network,
        )
        if not Promotion.objects.filter(status=Promotion.PromotionStatus.WAITING).exclude(id=promotion.id):
            promotion_checker.delay()
