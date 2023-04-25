from django.db.models.signals import post_save
from django.dispatch import receiver

from src.activity.models import (
    ActivitySubscription,
    BidsHistory,
    TokenHistory,
    UserAction,
)
from src.rates.api import calculate_amount


@receiver(post_save, sender=TokenHistory)
def token_history_post_save_dispatcher(sender, instance, created, *args, **kwargs):
    # create all ActivitySubscriptions for given activity
    calculate_usd_price(instance, sender)
    if created:
        receivers = instance.get_receivers()
        ActivitySubscription.create_subscriptions(sender, instance, receivers)


@receiver(post_save, sender=UserAction)
def user_action_post_save_dispatcher(sender, instance, created, *args, **kwargs):
    # create all ActivitySubscriptions for given activity
    if created:
        receivers = instance.get_receivers()
        ActivitySubscription.create_subscriptions(sender, instance, receivers)


@receiver(post_save, sender=BidsHistory)
def bids_history_post_save_dispatcher(sender, instance, created, *args, **kwargs):
    # create all ActivitySubscriptions for given activity
    if created:
        receivers = instance.get_receivers()
        ActivitySubscription.create_subscriptions(sender, instance, receivers)


def calculate_usd_price(token_history, sender):
    """
    Calculate usd price for token history.
    """
    if token_history.price and token_history.currency:
        token_history.USD_price = calculate_amount(
            token_history.price,
            token_history.currency.symbol,
        )
        post_save.disconnect(token_history_post_save_dispatcher, sender=sender)
        token_history.save(update_fields=["USD_price"])
        post_save.connect(token_history_post_save_dispatcher, sender=sender)
