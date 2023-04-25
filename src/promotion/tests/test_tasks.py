from datetime import timedelta

import pytest
from django.utils import timezone

from src.promotion.models import Promotion
from src.promotion.tasks import promotion_checker


@pytest.mark.django_db
def test_promotion_checker(mixer, promotion_setting):
    old_promotion, _ = mixer.cycle(2).blend(
        "promotion.Promotion",
        valid_until=timezone.now() + timedelta(hours=1),
        duration=timedelta(hours=1),
        status=Promotion.PromotionStatus.IN_PROGRESS,
        network=promotion_setting.network,
    )
    promotion = mixer.blend(
        "promotion.Promotion",
        duration=timedelta(days=2),
        status=Promotion.PromotionStatus.WAITING,
        network=promotion_setting.network,
    )

    # check slots limit
    promotion_checker()
    promotion.refresh_from_db()
    assert promotion.status == Promotion.PromotionStatus.WAITING

    # check promotion change routing
    old_promotion.valid_until = timezone.now()
    old_promotion.save(update_fields=("valid_until",))
    promotion_checker()
    promotion.refresh_from_db()
    old_promotion.refresh_from_db()
    assert old_promotion.status == Promotion.PromotionStatus.FINISHED
    assert promotion.status == Promotion.PromotionStatus.IN_PROGRESS
    assert (
        timezone.now() + timedelta(hours=47)
        < promotion.valid_until
        < timezone.now() + timedelta(hours=48)
    )
