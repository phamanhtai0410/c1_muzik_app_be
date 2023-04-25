import random

from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import Signal, receiver

from src.store.models import Collection, Status
from src.support.models import EmailTemplate
from src.support.tasks import send_email_notification

from .models import (
    DefaultGameAvatar,
    DefaultGameBanner,
    GameCategory,
    GameCompany,
    GameSubCategory,
)
from .signals_definition import game_approved
from .tasks import validate_game, validate_game_category, validate_game_subcategory


@receiver(pre_save, sender=GameCompany)
def game_pre_save_dispatcher(sender, instance, *args, **kwargs):
    unique_game_name_for_network_validator(instance)


@receiver(post_save, sender=GameCategory)
def game_category_post_save_dispatcher(sender, instance, *args, **kwargs):
    """
    start importing all collections after game is approved (via scanner)
    """
    if instance.is_approved:
        Collection.objects.filter(
            game_subcategory__category__id=instance.id, status=Status.PENDING
        ).update(status=Status.IMPORTING)
        GameSubCategory.objects.filter(category=instance).exclude(
            is_approved=True
        ).update(is_approved=True)


@receiver(post_save, sender=GameSubCategory)
def game_subcategory_post_save_dispatcher(sender, instance, *args, **kwargs):
    """
    start importing all collections after game is approved (via scanner)
    """
    if instance.is_approved:
        Collection.objects.filter(
            game_subcategory__id=instance.id, status=Status.PENDING
        ).update(status=Status.IMPORTING)


game_created = Signal(providing_args=["instance"])
category_added = Signal(providing_args=["instance"])
subcategory_added_updated = Signal(providing_args=["instance"])
category_approved = Signal(providing_args=["instance"])
subcategory_approved = Signal(providing_args=["instance"])
category_declined = Signal(providing_args=["instance"])
subcategory_declined = Signal(providing_args=["instance"])


@receiver(game_approved)
def game_approved_dispatcher(sender, instance, *args, **kwargs):
    """
    start importing all collections after game is approved (via scanner)
    """
    if kwargs.get("approved"):
        Collection.objects.filter(
            game_subcategory__category__game__id=instance.id, status=Status.PENDING
        ).update(status=Status.IMPORTING)
        GameCategory.objects.filter(game__id=instance.id).exclude(
            is_approved=True
        ).update(is_approved=True)
        GameSubCategory.objects.filter(category__game__id=instance.id).exclude(
            is_approved=True
        ).update(is_approved=True)
        set_default_game_values(instance)
        key = EmailTemplate.construct_email("GAME_APPROVED", instance, instance.email)
        if key:
            send_email_notification.apply_async(args=(key,), priority=3)
    else:
        Collection.objects.filter(game_subcategory__category__game=instance).update(
            game_subcategory=None
        )
        key = EmailTemplate.construct_email("GAME_DECLINED", instance, instance.email)
        if key:
            send_email_notification.apply_async(args=(key,), priority=3)


@receiver(game_created)
def validate_game_dispatcher(sender, instance, *args, **kwargs):
    """
    send creation notification to user
    start validating game after creation
    """
    key = EmailTemplate.construct_email("GAME_CREATED", instance, instance.email)
    if key:
        send_email_notification.apply_async(args=(key,), priority=3)
    validate_game.apply_async(args=(instance.id,), priority=4)


@receiver(category_added)
def validate_category_dispatcher(sender, instance, *args, **kwargs):
    """
    start validating game after creation
    """
    validate_game_category.apply_async(args=(instance.id,), priority=4)


@receiver(subcategory_added_updated)
def validate_subcategory_dispatcher(sender, instance, *args, **kwargs):
    """
    start validating game after creation
    """
    validate_game_subcategory.apply_async(args=(instance.id,), priority=4)


@receiver(category_approved)
def category_approved_dispatcher(sender, instance, *args, **kwargs):
    """
    send notification to user
    """
    key = EmailTemplate.construct_email(
        "CATEGORY_APPROVED", instance, instance.game.email
    )
    if key:
        send_email_notification.apply_async(args=(key,), priority=3)


@receiver(category_declined)
def category_declined_dispatcher(sender, instance, *args, **kwargs):
    """
    send notification to user
    """
    Collection.objects.filter(game_subcategory__category=instance).update(
        game_subcategory=None
    )
    key = EmailTemplate.construct_email(
        "CATEGORY_DECLINED", instance, instance.game.email
    )
    if key:
        send_email_notification.apply_async(args=(key,), priority=3)


@receiver(subcategory_approved)
def subcategory_approved_dispatcher(sender, instance, *args, **kwargs):
    """
    send notification to user
    """
    key = EmailTemplate.construct_email(
        "SUBCATEGORY_APPROVED", instance, instance.game.email
    )
    if key:
        send_email_notification.apply_async(args=(key,), priority=3)


@receiver(subcategory_declined)
def subcategory_declined_dispatcher(sender, instance, *args, **kwargs):
    """
    send notification to user
    """
    Collection.objects.filter(game_subcategory=instance).update(game_subcategory=None)
    key = EmailTemplate.construct_email(
        "SUBCATEGORY_DECLINED", instance, instance.game.email
    )
    if key:
        send_email_notification.apply_async(args=(key,), priority=3)


def set_default_game_values(game_instance):
    """
    Set default avatar and banner for game
    """

    image_field_models = {"avatar": DefaultGameAvatar, "banner": DefaultGameBanner}

    for image_field, image_model in image_field_models.items():
        if not getattr(game_instance, f"{image_field}_ipfs"):
            default_avatars = image_model.objects.all().values_list("image", flat=True)
            if default_avatars:
                setattr(
                    game_instance, f"{image_field}_ipfs", random.choice(default_avatars)
                )
    game_instance.save()


@receiver(post_delete, sender=GameCategory)
def category_post_delete_dispatcher(sender, instance, *args, **kwargs):
    key = EmailTemplate.construct_email(
        "CATEGORY_INVALID", instance, instance.game.email
    )
    if key:
        send_email_notification.apply_async(args=(key,), priority=3)


@receiver(post_delete, sender=GameSubCategory)
def subcategory_post_delete_dispatcher(sender, instance, *args, **kwargs):
    key = EmailTemplate.construct_email(
        "SUBCATEGORY_INVALID", instance, instance.game.email
    )
    if key:
        send_email_notification.apply_async(args=(key,), priority=3)


def unique_game_name_for_network_validator(game_company):
    """
    Raise exception if token with same name and network exists.
    """
    matching_game_company = GameCompany.objects.filter(
        name__iexact=game_company.name,
        network=game_company.network,
    ).exclude(is_approved=False)
    if game_company.id:
        matching_game_company = matching_game_company.exclude(id=game_company.id)
    if matching_game_company.exists():
        raise ValidationError("Game company name is occupied")
