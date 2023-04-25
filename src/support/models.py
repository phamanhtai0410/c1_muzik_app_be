import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import get_connection
from django.db import models
from django.forms import ValidationError
from django.utils import timezone
from django_quill.fields import QuillField

# from src.activity.models import TokenHistory
# from src.accounts.models import AdvUser
# from src.games.models import GameCompany
from src.settings import config
from src.utilities import RedisClient


class EmailConfig(models.Model):
    class EmailRole(models.TextChoices):
        RECEIVER = "Receiver"
        SENDER = "Sender"

    role = models.CharField(max_length=10, choices=EmailRole.choices)
    address = models.EmailField(max_length=200)
    password = models.CharField(max_length=100, null=True, blank=True)
    smtp = models.CharField(max_length=100, null=True, blank=True)
    port = models.IntegerField(null=True, blank=True)
    use_tls = models.BooleanField(default=False, null=True, blank=True)

    def __str__(self):
        return f"{self.role}Email"

    @classmethod
    def get_admin_receiver(cls) -> Optional[str]:
        instance = cls.objects.filter(role__iexact=cls.EmailRole.RECEIVER).first()
        if instance:
            return instance.address

    @classmethod
    def get_admin_sender(cls) -> "EmailConfig":
        return cls.objects.filter(role__iexact=cls.EmailRole.SENDER).first()

    def connection(
        self, smtp=None, port=None, username=None, password=None, use_tls=None
    ):
        return get_connection(
            host=smtp or self.smtp,
            port=port or self.port,
            username=username or self.address,
            password=password or self.password,
            use_tls=use_tls or self.use_tls,
        )


class Config(models.Model):
    top_users_period = models.IntegerField(
        null=True, blank=True, help_text="number of days"
    )
    top_collections_period = models.IntegerField(
        null=True, blank=True, help_text="number of days"
    )
    approval_timeout = models.IntegerField(
        help_text="frequency of approval revoke scanner in seconds"
    )
    max_royalty_percentage = models.DecimalField(
        max_digits=3, decimal_places=1, help_text="maximum percentage value for royalty"
    )

    def __str__(self):
        return "Config"

    @classmethod
    def object(cls):
        return cls._default_manager.all().first()  # Since only one item

    def save(self, *args, **kwargs):
        if not self.pk and Config.objects.exists():
            raise ValidationError("There can be only one Config instance")
        return super(Config, self).save(*args, **kwargs)

    @classmethod
    def get_top_collections_period(cls):
        config_object = cls.object()
        if not config_object or not config_object.top_collections_period:
            return timezone.make_aware(datetime.fromtimestamp(0)), "all"
        return (
            timezone.now() - timedelta(days=config_object.top_collections_period),
            config_object.top_collections_period,
        )

    @classmethod
    def get_top_users_period(cls):
        config_object = cls.object()
        now = timezone.now()
        if not config_object or not config_object.top_users_period:
            return (
                timezone.make_aware(datetime.fromtimestamp(0)),
                "all",
            )  # if period not set, counts as "all time"
        return (
            now - timedelta(days=config_object.top_users_period),
            config_object.top_users_period,
        )

    @property
    def sales_amount(self):
        token_history_model = apps.get_model("activity.TokenHistory")
        return token_history_model.objects.filter(
            method__in=["AuctionWin", "Buy"]
        ).count()

    @property
    def sales_volume(self):
        token_history_model = apps.get_model("activity.TokenHistory")
        return f'{token_history_model.objects.filter(method__in=["AuctionWin", "Buy"]).aggregate(volume=models.Sum("USD_price"))["volume"]}$'

    @property
    def user_emails(self):
        user_model = apps.get_model("accounts.AdvUser")
        game_model = apps.get_model("games.GameCompany")
        user_emails = list(
            user_model.objects.filter(email__isnull=False).values_list(
                "email", flat=True
            )
        )
        game_emails = list(
            game_model.objects.filter(email__isnull=False).values_list(
                "email", flat=True
            )
        )
        return ", ".join(
            email for email in list(set(user_emails + game_emails))
        ).lstrip(", ")


class EmailTemplate(models.Model):
    class MessageType(models.TextChoices):
        GAME_CREATED = "Game created"
        CONTRACT_INVALID = "Contract invalid"
        CATEGORY_INVALID = "Category invalid"
        SUBCATEGORY_INVALID = "Subcategory invalid"
        GAME_APPROVED = "Game approved"
        GAME_DECLINED = "Game declined"
        GAME_SYNCED = "Game synced"
        CONTRACT_APPROVED = "Contract approved"
        CATEGORY_APPROVED = "Category approved"
        SUBCATEGORY_APPROVED = "Subcategory approved"
        CATEGORY_DECLINED = "Category declined"
        CONTRACT_DECLINED = "Contract declined"
        SUBCATEGORY_DECLINED = "Subcategory declined"
        NEW_EVENT = "New event happened"

    message_type = models.CharField(
        max_length=100, choices=MessageType.choices, unique=True
    )
    topic = models.CharField(max_length=100, default="Topic")
    text = QuillField(blank=True, null=True, default=None)

    def __str__(self):
        return self.message_type

    def render_body(self, instance):
        text = json.loads(self.text.json_string).get("html")
        data = {}
        fields = instance.email_fields
        for field in fields:
            try:
                data[f"{field}"] = fields[field]
            except ObjectDoesNotExist:
                continue
        main_text = text.format(**data)
        return main_text

    def render_topic(self):
        return f"{config.TITLE}: {self.topic}"

    @classmethod
    def construct_email(cls, message_type, instance, receiver_address):
        """
        build message and cache it in redis for 30 minutes (enough to send)
        """
        if not receiver_address:
            logging.warning("admin receiver not set, skipping")
        template = cls.objects.filter(
            message_type=getattr(cls.MessageType, message_type, None)
        ).first()
        if not template:
            logging.warning(f"template {message_type} not found")
            return
        try:
            data = {
                "receiver": receiver_address,
                "topic": template.render_topic(),
                "text": template.render_body(instance),
            }
            key = datetime.now().timestamp()
        except Exception as e:
            logging.error(f"email construct failed with error {repr(e)}")
            return
        connection = RedisClient().connection
        connection.set(key, json.dumps(data), ex=1800)
        return key

    @property
    def hints(self):
        fields = self.field_list.get(
            f"{self.message_type.split(' ')[0].lower()}_fields"
        )
        text = f"available placeholders: {fields}"
        text += "\n Example of placeholders usage: Hi, {user_name}!"
        return text

    @property
    def field_list(self):
        return {
            "game_fields": "user_name, game_name, network, email, contact_email",
            "category_fields": "category_name, user_name, game_name, network, email, contact_email",
            "subcategory_fields": "subcategory_name, category_name, user_name, game_name, network, email, contact_email",
            "contract_fields": "collection_name, collection_address, subcategory_name, category_name, user_name, game_name, network, email, contact_email",
        }
