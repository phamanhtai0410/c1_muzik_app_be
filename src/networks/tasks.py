from celery import shared_task
from src.bot.services import send_message
from src.networks.models import Network
from src.settings import config
from src.utilities import alert_bot


@shared_task(name="balance_checker")
@alert_bot
def balance_checker():
    alerts = ""
    for network in Network.objects.all():
        balance = network.get_signer_balance()
        if balance < network.minimal_balance * 10 ** 18:
            alerts += (
                f"balance in {network.name} is lower than minimal accepted: {float(balance) / 10 ** 18}"
                f" {network.native_symbol}, please top up the balance at address {config.SIGNER_ADDRESS}\n"
            )
    if alerts:
        send_message(alerts, ["trade"])
