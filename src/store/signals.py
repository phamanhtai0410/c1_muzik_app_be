import random

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import Signal, receiver

from src.accounts.models import DefaultAvatar
from src.games.tasks import validate_game_collection
from src.promotion.models import Promotion
from src.store.models import Collection, Ownership, Status, Token, TransactionTracker
from src.support.models import EmailTemplate
from src.support.tasks import send_email_notification
from src.utilities import RedisClient


@receiver(pre_save, sender=Collection)
def collection_pre_save_dispatcher(sender, instance, *args, **kwargs):
    """
    check if it is the last synced collection in game
    """
    check_is_synced(instance)


@receiver(post_save, sender=Collection)
def collection_post_save_dispatcher(sender, instance, created, *args, **kwargs):
    update_delete_status(instance)
    set_default_values(instance, created)


@receiver(post_delete, sender=Collection)
def collection_post_delete_dispatcher(sender, instance, *args, **kwargs):
    if instance.game:
        key = EmailTemplate.construct_email(
            "CONTRACT_INVALID", instance, instance.game.email
        )
        if key:
            send_email_notification.apply_async(args=(key,), priority=3)


@receiver(pre_save, sender=Token)
def token_pre_save_dispatcher(sender, instance, *args, **kwargs):
    if not instance.id:
        unique_name_for_network_validator(instance)
        set_mint_id(instance)


@receiver(post_save, sender=Token)
def token_post_save_dispatcher(sender, instance, *args, **kwargs):
    if instance.status == Status.COMMITTED:
        connection = RedisClient().connection
        connection.set(f"queue_calculate_rarity{instance.collection.id}", 1)


collection_added = Signal(providing_args=["instance"])
collection_restored = Signal(providing_args=["instance"])
collection_approved = Signal(providing_args=["instance"])
collection_declined = Signal(providing_args=["instance"])


@receiver(collection_added)
def validate_collection(sender, instance, *args, **kwargs):
    """
    validate collection added to game
    """
    validate_game_collection.apply_async(args=(instance.id,), priority=4)


@receiver(collection_restored)
def restore_collection_tokens(sender, instance, *args, **kwargs):
    """
    restore tokens after collection restore
    """
    instance.tokens.update(deleted=False)


@receiver(collection_approved)
def collection_approved_dispatcher(sender, instance, *args, **kwargs):
    """
    send notification to user
    """
    key = EmailTemplate.construct_email(
        "CONTRACT_APPROVED", instance, instance.game.email
    )
    if key:
        send_email_notification.apply_async(args=(key,), priority=3)


@receiver(collection_declined)
def collection_declined_dispatcher(sender, instance, *args, **kwargs):
    """
    send notification to user
    """
    key = EmailTemplate.construct_email(
        "CONTRACT_DECLINED", instance, instance.game.email
    )
    if key:
        send_email_notification.apply_async(args=(key,), priority=3)


def set_mint_id(token):
    last_token = token.collection.tokens.order_by("mint_id").last()
    mint_id = last_token.mint_id + 1 if last_token else 0
    token.mint_id = mint_id


@receiver(post_save, sender=Ownership)
@transaction.atomic
def ownership_post_save_dispatcher(sender, instance, created, *args, **kwargs):
    selling_quantity_validate(instance, sender)
    check_quantity_exists(instance)


@receiver(post_delete, sender=Ownership)
def ownership_post_delete_dispatcher(sender, instance, *args, **kwargs):
    Promotion.objects.filter(owner=instance, token=instance.token).update(
        status=Promotion.PromotionStatus.FINISHED
    )


def unique_name_for_network_validator(token):
    """
    Raise exception if token with same name and network exists.
    """
    matching_token = Token.objects.filter(
        name=token.name,
        collection__network=token.collection.network,
    )
    if token.id:
        matching_token = matching_token.exclude(id=token.id)
    if matching_token.exists():
        raise ValidationError("Name is occupied")


def update_delete_status(collection):
    """
    If collection DELETED, change collection tokens on DELETED.
    """
    if collection.deleted:
        collection.tokens.update(deleted=True)


def set_default_values(collection, created):
    """
    Set default avatar and address for collection.
    """
    if created and not collection.avatar_ipfs:
        default_avatars = DefaultAvatar.objects.all().values_list("image", flat=True)
        if default_avatars:
            collection.avatar_ipfs = random.choice(default_avatars)
            collection.save()


def selling_quantity_validate(ownership, sender):
    """
    Validate selling quantity.
    If ownership not for sale selling_qantity is 0.
    Set to selling_qantity min from (quantity, selling_qantity).
    """
    if (
        not ownership.selling
        and not TransactionTracker.objects.filter(ownership=ownership).exists()
    ):
        ownership.selling_quantity = 0
    ownership.selling_quantity = min(ownership.selling_quantity, ownership.quantity)
    if ownership.selling_quantity == 0:
        ownership.selling = False
        ownership.price = None
        ownership.currency = None
        if ownership.token.is_single:
            ownership.token.bids.all().delete()
    post_save.disconnect(ownership_post_save_dispatcher, sender=sender)
    ownership.save(update_fields=["selling", "selling_quantity", "currency", "price"])
    post_save.connect(ownership_post_save_dispatcher, sender=sender)


def check_quantity_exists(ownership):
    if ownership.quantity <= 0:
        try:
            ownership.delete()
        except AssertionError:
            return


def check_is_synced(collection):
    if (
        collection.id
        and collection.is_imported
        and collection.status == Status.COMMITTED
        and collection.game
    ):
        previous_state = Collection.objects.get(id=collection.id).status
        if (
            previous_state == Status.IMPORTING
            and not Collection.objects.filter(
                game_subcategory__category__game=collection.game,
                status=Status.IMPORTING,
            )
            .exclude(id=collection.id)
            .exists()
        ):
            key = EmailTemplate.construct_email(
                "GAME_SYNCED", collection.game, collection.game.email
            )
            print(f"sending mail to {collection.game.email}")
            if key:
                send_email_notification.apply_async(args=(key,), priority=3)
