from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Q

from src.settings import config
from src.utilities import get_media_from_ipfs


class DefaultAvatar(models.Model):
    image = models.CharField(max_length=200, blank=True, null=True, default=None)

    @property
    def ipfs_image(self):
        return get_media_from_ipfs(self.image)


class AdvUserManager(UserManager):
    def get_by_custom_url(self, value):
        """
        Return user by id or custom_url.

        Convert param to int() if it contains only digitts, because string params are not allowed
        in searching by id field. Numeric custom_urls should be prohibited on frontend
        """
        if value is None:
            raise ObjectDoesNotExist
        user_id = None
        if isinstance(value, int) or value.isdigit():
            user_id = int(value)
        # get by id or set field
        return self.get(Q(id=user_id) | Q(**{config.USER_URL_FIELD: value}))


class AdvUser(AbstractUser):
    avatar_ipfs = models.CharField(max_length=200, null=True, default=None)
    cover_ipfs = models.CharField(max_length=200, null=True, default=None, blank=True)
    display_name = models.CharField(max_length=50, default=None, null=True, blank=True)
    custom_url = models.CharField(
        max_length=80, default=None, null=True, blank=True, unique=True
    )
    bio = models.TextField(default=None, null=True, blank=True)
    twitter = models.CharField(max_length=80, default=None, null=True, blank=True)
    instagram = models.CharField(max_length=80, default=None, null=True, blank=True)
    facebook = models.CharField(max_length=80, default=None, null=True, blank=True)
    site = models.CharField(max_length=200, default=None, null=True, blank=True)
    is_verificated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    metamask_message = models.CharField(max_length=30, null=True)

    objects = AdvUserManager()

    def get_name(self) -> str:
        return self.display_name or self.username

    def __str__(self) -> str:
        return self.get_name()

    @property
    def avatar(self) -> str:
        return get_media_from_ipfs(self.avatar_ipfs)

    @property
    def cover(self) -> str:
        return get_media_from_ipfs(self.cover_ipfs)

    @property
    def url(self) -> str:
        return (
            getattr(self, config.USER_URL_FIELD)
            if getattr(self, config.USER_URL_FIELD)
            else self.id
        )
