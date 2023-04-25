import json
import logging
from datetime import datetime, timedelta
from itertools import chain
from typing import Optional

from django.db import transaction
from django.utils import timezone

from celery import shared_task
from src.activity.models import TokenHistory
from src.decorators import ignore_duplicates
from src.networks.models import Network, Types
from src.rates.models import UsdRate
from src.settings import config
from src.store.exchange import TokenExchange
from src.store.models import (
    Bid,
    Collection,
    Ownership,
    Status,
    Tags,
    Token,
    TransactionTracker,
)
from src.utilities import RedisClient, alert_bot, check_tx

logger = logging.getLogger("celery")


@shared_task(name="remove_pending")
def remove_pending():
    expiration_date = datetime.today() - timedelta(
        minutes=config.PENDING_EXPIRATION_MINUTES
    )
    kwargs = {
        "status__in": (Status.PENDING, Status.FAILED),
        "created_at__lte": expiration_date,
    }
    Token.objects.filter(**kwargs).delete()
    # exclude imported collections
    kwargs["is_imported"] = False
    Collection.objects.filter(**kwargs).delete()
    logger.info("Pending items deleted")


@shared_task(name="remove_token_tag_new")
def remove_token_tag_new():
    tag = Tags.objects.filter(name="New").first()
    if tag is None:
        return
    tokens = Token.objects.filter(
        created_at__lte=datetime.today()
        - timedelta(hours=config.CLEAR_TOKEN_TAG_NEW_TIME),
    )
    for token in tokens:
        token.tags.remove(tag)


@shared_task(name="end_auction_checker")
@alert_bot
def end_auction_checker():
    for network in Network.objects.all():
        end_auction_executer.apply_async(
            args=(network.id,),
        )


@shared_task(name="end_auction_executer")
@alert_bot
def end_auction_executer(network_id):
    network = Network.objects.get(id=network_id)
    ownerships = Ownership.objects.filter(
        _end_auction__lte=timezone.now(), token__collection__network=network
    )
    tokens = [o.token for o in ownerships]
    tokens = list(set(tokens))[:20]

    if not tokens:
        return

    tx_hash, history_data = TokenExchange.end_auction_send(tokens)

    if tx_hash is None:
        return

    res = check_tx(tx_hash, network)
    if not res:
        return

    for data in history_data:
        with transaction.atomic():
            currency = UsdRate.objects.first()
            token = Token.objects.get(id=data.get("id"))
            ownership = token.ownerships.first()
            ownership.owner = data.get("new_owner")
            ownership.save(update_fields=["owner"])
            TokenHistory.objects.update_or_create(
                tx_hash=tx_hash,
                token=token,
                defaults={
                    "method": "AuctionWin",
                    "price": data.get("amount"),
                    "new_owner": data.get("new_owner"),
                    "old_owner": data.get("old_owner"),
                    "currency": currency,
                },
            )
            token.bids.all().delete()
            token.controller.change_sell_status(data.get("new_owner"))


@shared_task(name="incorrect_bid_checker")
@alert_bot
def incorrect_bid_checker():
    bids = Bid.objects.committed()
    for bid in bids:
        validator = bid.token.validator
        validator.check_validate_bid(user=bid.user, amount=bid.amount)
        if validator.errors is not None:
            bid.state = Status.EXPIRED
            bid.save()


def check_ethereum_transactions(tx) -> bool:
    w3 = tx.token.collection.network.web3
    transaction = w3.eth.getTransactionReceipt(tx.tx_hash)
    logger.info(f"Transaction status success - {bool(transaction.get('status'))}")
    return bool(transaction.get("status"))


def check_transaction_status(tx, network_type) -> Optional[bool]:
    try:
        if network_type == "ethereum":
            return check_ethereum_transactions(tx)
    except Exception as e:
        logger.warning(f"Transaction not yet mined. Error: {e}")
        return None


@shared_task(name="transaction_tracker")
@alert_bot
def transaction_tracker():
    # delete expired blockers
    now = timezone.now()
    delta = timedelta(seconds=config.TX_TRACKER_TIMEOUT)
    expired_tx_list = TransactionTracker.objects.filter(tx_hash__isnull=True).filter(
        created_at__lt=now - delta
    )
    id_list = expired_tx_list.values_list("ownership__id", flat=True)
    owners = Ownership.objects.filter(id__in=id_list)
    owners.update(selling=True)
    expired_tx_list.delete()

    # check transactions
    for network_type in Types._member_names_:
        tx_list = TransactionTracker.objects.filter(
            token__collection__network__network_type=network_type
        )
        for tx in tx_list:
            is_success = check_transaction_status(tx, network_type)
            if is_success is not None:
                if not is_success:
                    tx.ownership.selling = True
                    tx.ownership.save()
                tx.delete()


@shared_task(name="calculate_rarity_starter")
@alert_bot
@ignore_duplicates
def calculate_rarity_starter():
    connection = RedisClient().connection
    for key in connection.keys("queue_calculate_rarity*"):
        calculate_rarity.apply_async(
            args=(int(key.lstrip("queue_calculate_rarity")),), priority=3
        )
        connection.delete(key)


@shared_task(name="calculate_rarity")
@alert_bot
@ignore_duplicates
def calculate_rarity(col_id):
    data = {}
    collection = Collection.objects.get(id=col_id)
    tokens = collection.tokens.committed()
    tokens_amount = tokens.count()
    trait_types_list = list(
        set(
            chain.from_iterable(
                tokens.filter(_properties__isnull=False).values_list(
                    "_properties", flat=True
                )
            )
        )
    )
    for trait_type in trait_types_list:
        filter_data = {f"_properties__{trait_type}__trait_type": trait_type}
        # get list of values for each atribute and count their amount
        perks_list = list(
            set(
                tokens.filter(**filter_data).values_list(
                    f"_properties__{trait_type}__trait_value", flat=True
                )
            )
        )
        data[trait_type] = {"amount": len(perks_list), "perks": {}}
        # get frequency of each attribute
        for perk in perks_list:
            filter_data = {f"_properties__{trait_type}__trait_value": perk}
            amount = tokens.filter(**filter_data).count()
            rarity = amount / tokens_amount * 100
            data[trait_type]["perks"][str(perk)] = {"amount": amount, "rarity": rarity}
    connection = RedisClient().connection
    key = f"perks_{collection.id}"
    connection.set(
        key,
        json.dumps(data, ensure_ascii=False, default=str),
    )
