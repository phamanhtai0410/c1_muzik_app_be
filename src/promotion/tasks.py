from django.utils import timezone

from celery import shared_task
from src.promotion.models import Promotion, PromotionSettings
from src.utilities import alert_bot


@shared_task(name="promotion_checker")
@alert_bot
def promotion_checker() -> None:
    # finish promotions by time
    Promotion.objects.filter(
        status=Promotion.PromotionStatus.IN_PROGRESS, valid_until__lte=timezone.now()
    ).update(status=Promotion.PromotionStatus.FINISHED)
    # activate new promotions
    for settings in PromotionSettings.objects.all():
        active_promotions_count = Promotion.objects.filter(
            status=Promotion.PromotionStatus.IN_PROGRESS, network=settings.network
        ).count()
        waiting_promotions = Promotion.objects.filter(
            status=Promotion.PromotionStatus.WAITING, network=settings.network
        ).order_by("pk")[: max(settings.slots - active_promotions_count, 0)]
        for promotion in waiting_promotions:
            promotion.status = Promotion.PromotionStatus.IN_PROGRESS
            promotion.valid_until = timezone.now() + promotion.duration
            promotion.save()
