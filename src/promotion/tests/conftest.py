import pytest


@pytest.fixture
def promotion_setting(mixer):
    # create initial promotion setting
    return mixer.blend("promotion.PromotionSettings", slots=2)


@pytest.fixture
def promotion_option_first(mixer, promotion_setting):
    # create initial promotion setting
    return mixer.blend(
        "promotion.PromotionOptions",
        days=1,
        usd_price=10,
        promotion=promotion_setting,
        package=None,
    )


@pytest.fixture
def promotion_option_second(mixer, promotion_setting):
    # create initial promotion setting
    return mixer.blend(
        "promotion.PromotionOptions",
        days=2,
        usd_price=20,
        promotion=promotion_setting,
        package=None,
    )
