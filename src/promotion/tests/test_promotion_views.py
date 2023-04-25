from datetime import timedelta

import pytest
from django.utils import timezone

from src.promotion.models import Promotion
from src.promotion.serializers import PromotionOptionsSerializer


@pytest.mark.django_db
def test_promotion_view(
    mixer, auth_api, promotion_setting, promotion_option_first, promotion_option_second
):
    # check base view and serialization
    response = auth_api.get("/api/v1/promotion/")
    assert response.status_code == 200
    assert response.json()[0]["slots"] == promotion_setting.slots
    assert response.json()[0]["available_slots"] == promotion_setting.slots
    assert response.json()[0]["options"][0] == dict(
        PromotionOptionsSerializer(promotion_option_first).data
    )
    assert response.json()[0]["options"][1] == dict(
        PromotionOptionsSerializer(promotion_option_second).data
    )

    # check available slots calculation
    mixer.blend(
        "promotion.Promotion",
        valid_until=timezone.now() + timedelta(days=2),
        duration=timedelta(days=2),
        status=Promotion.PromotionStatus.IN_PROGRESS,
        network=promotion_setting.network,
    )
    response = auth_api.get("/api/v1/promotion/")
    assert response.status_code == 200
    assert response.json()[0]["available_slots"] == promotion_setting.slots - 1
