import pytest


@pytest.mark.django_db
def test_package(
    mixer, promotion_setting, promotion_option_first, promotion_option_second
):
    # check assignment in order
    promotion_option_third = mixer.blend(
        "promotion.PromotionOptions",
        days=2,
        usd_price=20,
        promotion=promotion_setting,
        package=None,
    )
    assert promotion_option_third.package == promotion_option_second.package + 1

    # check package reassignment
    free_number = promotion_option_first.package
    promotion_option_first.delete()
    new_promotion = mixer.blend(
        "promotion.PromotionOptions",
        days=1,
        usd_price=10,
        promotion=promotion_setting,
        package=None,
    )
    assert new_promotion.package == free_number
