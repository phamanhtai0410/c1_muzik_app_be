import re
from typing import Dict, Optional, Union

from django.db import models

from src.accounts.models import AdvUser
from src.activity.services.subscriptor import Subscriptor
from src.consts import MAX_AMOUNT_LEN

pattern = re.compile(r"(?<!^)(?=[A-Z])")


class UserAction(models.Model):
    whom_follow = models.ForeignKey(
        "accounts.AdvUser",
        related_name="following",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    user = models.ForeignKey(
        "accounts.AdvUser", related_name="followers", on_delete=models.CASCADE
    )
    date = models.DateTimeField(auto_now_add=True, db_index=True)
    method = models.CharField(
        choices=[("like", "like"), ("follow", "follow")], max_length=6, default="follow"
    )
    token = models.ForeignKey(
        "store.Token",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        default=None,
        related_name="likes",
    )

    def get_receivers(self):
        """get initial receivers for subscription model"""
        # follower liked of followed
        initial_receivers = {}
        if not self.token or not self.token.owners.filter(id=self.user.id):
            initial_receivers[self.user] = "follow"
        # I was followed or my token was liked
        if self.method == "follow":
            initial_receivers[self.whom_follow] = "self"
        elif self.method == "like":
            initial_receivers = {
                **initial_receivers,
                **dict.fromkeys(self.token.owners.exclude(id=self.user.id), "self"),
            }
        return initial_receivers

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["whom_follow", "user"], name="unique_followers"
            ),
            models.UniqueConstraint(fields=["user", "token"], name="unique_likes"),
        ]

        ordering = ["-date"]


class History(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    price = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN,
        decimal_places=18,
        default=None,
        blank=True,
        null=True,
    )
    currency = models.ForeignKey(
        "rates.UsdRate", on_delete=models.PROTECT, null=True, default=None, blank=True
    )

    class Meta:
        abstract = True


class TokenHistory(History):
    token = models.ForeignKey(
        "store.Token", on_delete=models.CASCADE, related_name="history"
    )
    tx_hash = models.CharField(max_length=200)
    method = models.CharField(
        max_length=10,
        choices=[
            ("Transfer", "Transfer"),
            ("Buy", "Buy"),
            ("Mint", "Mint"),
            ("Burn", "Burn"),
            ("Listing", "Listing"),
            ("AuctionWin", "AuctionWin"),
        ],
        default="Transfer",
    )
    new_owner = models.ForeignKey(
        "accounts.AdvUser",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="new_owner",
    )
    old_owner = models.ForeignKey(
        "accounts.AdvUser",
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="old_owner",
    )
    USD_price = models.DecimalField(
        max_digits=18, decimal_places=2, default=None, blank=True, null=True
    )
    amount = models.PositiveIntegerField(default=None, blank=True, null=True)

    def get_receivers(self):
        # get initial receivers for subscription model
        initial_receivers = {}
        # follower minter, listed, sold
        if self.method in ["Listing", "Mint", "Transfer"]:
            initial_receivers[self.old_owner] = "follow"
        # auction winning is valid for both filters
        if self.method in ["AuctionWin"]:
            initial_receivers[self.new_owner] = "both"
        # follower bought from me
        if self.method == "Buy":
            initial_receivers[self.old_owner] = "self"
            initial_receivers[self.new_owner] = "follow"
        return initial_receivers

    class Meta:
        verbose_name_plural = "Token History"


class BidsHistory(History):
    token = models.ForeignKey(
        "store.Token", on_delete=models.CASCADE, related_name="bids_history"
    )
    user = models.ForeignKey("accounts.AdvUser", on_delete=models.CASCADE)
    method = models.CharField(choices=[("Bet", "Bet")], default="Bet", max_length=3)

    def get_receivers(self):
        # get initial receivers for subscription model
        # follower bidded
        initial_receivers = {
            self.user: "follow",
        }
        # somebody bidded on me
        seller_ids = self.token.ownerships.filter(selling=True).values_list(
            "owner", flat=True
        )
        initial_receivers = {
            **initial_receivers,
            **dict.fromkeys(AdvUser.objects.filter(id__in=seller_ids), "self"),
        }
        return initial_receivers

    class Meta:
        verbose_name_plural = "Bids History"


class ActivitySubscription(models.Model):
    # links to triggering activity
    token_history = models.ForeignKey(
        "TokenHistory",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="subscriptions",
    )
    bids_history = models.ForeignKey(
        "BidsHistory",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="subscriptions",
    )
    user_action = models.ForeignKey(
        "UserAction",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="subscriptions",
    )

    # used for deleting only
    source = models.ForeignKey(
        "accounts.AdvUser",
        on_delete=models.CASCADE,
        related_name="subscriptors",
        blank=True,
        null=True,
    )
    # whom to show notification
    receiver = models.ForeignKey(
        "accounts.AdvUser", on_delete=models.CASCADE, related_name="subscriptions"
    )
    type = models.CharField(max_length=10)
    method = models.CharField(
        max_length=20,
        null=True,
        choices=[
            ("Transfer", "Transfer"),
            ("Buy", "Buy"),
            ("Mint", "Mint"),
            ("Burn", "Burn"),
            ("Listing", "Listing"),
            ("AuctionWin", "AuctionWin"),
            ("like", "like"),
            ("follow", "follow"),
            ("Bet", "Bet"),
        ],
    )
    date = models.DateTimeField()

    is_viewed = models.BooleanField(default=False)

    @property
    def activity(self):
        # only one could be set
        return self.token_history or self.bids_history or self.user_action

    @property
    def valid_for_notification(self):
        valid_for_self_notification = (
            self.type in ["self", "both"] and self.source is None
        )
        valid_for_following_notification = (
            self.type in ["follow", "both"] and self.source is not None
        )
        return valid_for_following_notification or valid_for_self_notification

    @classmethod
    def _create_subscription(
        cls,
        model: "models.Model",
        instance: Union["UserAction", "BidsHistory", "TokenHistory"],
        receiver: "AdvUser",
        view_type: str,
        source: Optional["AdvUser"] = None,
    ) -> None:
        method = instance.method
        sub_instance = cls(
            receiver=receiver,
            source=source,
            date=instance.date,
            type=view_type,
            method=method,
        )
        # get snake_case field name from camelModelName
        field_name = pattern.sub("_", model.__name__).lower()
        setattr(sub_instance, field_name, instance)
        sub_instance.save()

    @classmethod
    def create_subscriptions(
        cls,
        model: "models.Model",
        instance: Union["UserAction", "BidsHistory", "TokenHistory"],
        receivers: Dict["AdvUser", str],
    ) -> None:
        processed_receivers = []
        for receiver in receivers.keys():
            if receivers[receiver] in ["follow", "both"]:
                # add subscription for followers
                additional_receivers = Subscriptor().add_subscriptors(receiver)
                for additional_receiver in additional_receivers.keys():
                    # exclude initial receivers to avoid duplicates and track already created
                    if (
                        additional_receiver not in receivers
                        and additional_receiver not in processed_receivers
                    ):
                        processed_receivers.append(additional_receiver)
                        cls._create_subscription(
                            model,
                            instance,
                            additional_receiver,
                            additional_receivers[additional_receiver],
                            receiver,
                        )

            # add subscription for main user
            cls._create_subscription(model, instance, receiver, receivers[receiver])

    class Meta:
        # prevent setting multiple or none activity links on db setting
        constraints = [
            models.CheckConstraint(
                name="only one activity is set",
                check=(
                    models.Q(
                        token_history__isnull=False,
                        bids_history__isnull=True,
                        user_action__isnull=True,
                    )
                    | models.Q(
                        token_history__isnull=True,
                        bids_history__isnull=False,
                        user_action__isnull=True,
                    )
                    | models.Q(
                        token_history__isnull=True,
                        bids_history__isnull=True,
                        user_action__isnull=False,
                    )
                ),
            )
        ]


class UserStat(models.Model):
    network = models.ForeignKey(
        "networks.Network", on_delete=models.CASCADE, null=True, blank=True
    )
    user = models.ForeignKey("accounts.AdvUser", on_delete=models.CASCADE)
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=None,
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.user.get_name()


class CollectionStat(models.Model):
    collection = models.ForeignKey(
        "store.Collection", on_delete=models.CASCADE, related_name="stats"
    )
    date = models.DateField()
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=None,
        blank=True,
        null=True,
    )
    average_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=None,
        blank=True,
        null=True,
    )
    number_of_trades = models.IntegerField(null=True)

    def __str__(self):
        return f"{self.collection} {self.date}"
