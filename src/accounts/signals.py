import random

from django.db.models.signals import post_save
from django.dispatch import receiver

from src.accounts.models import AdvUser, DefaultAvatar


@receiver(post_save, sender=AdvUser)
def adv_user_post_save_dispatcher(sender, instance, created, *args, **kwargs):
    set_default_avatar(instance, created)


def set_default_avatar(adv_user, created):
    """
    Set default avatar for user.
    """
    if created:
        default_avatars = DefaultAvatar.objects.all().values_list("image", flat=True)
        if default_avatars:
            adv_user.avatar_ipfs = random.choice(default_avatars)
            adv_user.save()
