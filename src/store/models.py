import json
import time
from datetime import datetime
from typing import Optional

import requests
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from src.consts import MAX_AMOUNT_LEN, TOKEN_MINT_GAS_LIMIT
from src.networks.models import Network
from src.settings import config
from src.store.controllers import TokenController
from src.store.exchange import CollectionExchange, TokenExchange
from src.store.validators import TokenValidator
from src.support.models import EmailConfig
from src.support.validators import royalty_max_value_validator
from src.utilities import RedisClient, get_media_from_ipfs

from .services.ipfs import get_ipfs_by_hash


class Status(models.TextChoices):
    PENDING = "Pending"
    FAILED = "Failed"
    COMMITTED = "Committed"
    BURNED = "Burned"
    EXPIRED = "Expired"
    IMPORTING = "Importing"


class CollectionQuerySet(models.QuerySet):
    def committed(self):
        return self.filter(deleted=False, status=Status.COMMITTED)

    def scannerable(self):
        return self.filter(deleted=False).filter(
            status__in=[Status.COMMITTED, Status.IMPORTING]
        )

    def get_by_short_url(self, short_url):
        collection_id = None
        if short_url and (isinstance(short_url, int) or short_url.isdigit()):
            collection_id = int(short_url)
        return self.get(Q(id=collection_id) | Q(short_url=short_url))

    def user_collections(self, user, network=None):
        if user:
            assert (
                user.is_authenticated
            ), "Getting collections for an unauthenticated user"
        items = self.filter(status=Status.COMMITTED, is_imported=False).filter(
            Q(is_default=True) | Q(creator=user), deleted=False
        )
        if network and network != "undefined":
            items = items.filter(network__name__icontains=network)
        return items.order_by("-is_default")

    def network(self, network):
        if network is None or network == "undefined":
            return self
        return self.filter(network__name__icontains=network)

    def category(self, category):
        if not category:
            return self
        return self.filter(
            Exists(
                Token.objects.committed().filter(
                    category__name=category,
                    collection__id=OuterRef("id"),
                )
            )
        )

    def game(self, game_name):
        if not game_name:
            return self
        return self.filter(game_category__game__name__iexact=game_name)

    def game_category(self, game_category_name):
        if not game_category_name:
            return self
        return self.filter(game_category__name__iexact=game_category_name)


class CollectionManager(models.Manager):
    def get_queryset(self):
        return CollectionQuerySet(self.model, using=self._db)

    def committed(self):
        return self.get_queryset().committed()

    def scannerable(self):
        return self.get_queryset().scannerable()

    def get_by_short_url(self, short_url):
        """Return collection by id or short_url"""
        return self.get_queryset().get_by_short_url(short_url)

    def user_collections(self, user, network=None):
        """Return collections for user (with default collections)"""
        return self.get_queryset().user_collections(user, network)

    def network(self, network):
        """Return collections filtered by network name"""
        return self.get_queryset().network(network)

    def category(self, category):
        """Return collections filtered by exists token with tag"""
        return self.get_queryset().category(category)

    def game(self, game_name):
        """Return collections filtered by exists token with tag"""
        return self.get_queryset().game(game_name)

    def game_category(self, game_category_name):
        """Return collections filtered by exists token with tag"""
        return self.get_queryset().game_category(game_category_name)


class Collection(models.Model):
    name = models.CharField(max_length=100, null=True)
    avatar_ipfs = models.CharField(max_length=200, null=True, default=None)
    cover_ipfs = models.CharField(max_length=200, null=True, default=None, blank=True)
    address = models.CharField(max_length=60, null=True, blank=True)
    symbol = models.CharField(max_length=30, null=True)
    description = models.TextField(null=True, blank=True)
    standard = models.CharField(
        max_length=10,
        choices=[("ERC721", "ERC721"), ("ERC1155", "ERC1155")],
    )
    short_url = models.CharField(
        max_length=30,
        default=None,
        null=True,
        blank=True,
        unique=True,
    )
    creator = models.ForeignKey(
        "accounts.AdvUser",
        on_delete=models.PROTECT,
        null=True,
        default=None,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMMITTED,
    )
    deploy_block = models.IntegerField(blank=True, null=True, default=None)
    network = models.ForeignKey("networks.Network", on_delete=models.CASCADE)
    is_default = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    creator_royalty = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        validators=[royalty_max_value_validator],
    )
    game_subcategory = models.ForeignKey(
        "games.GameSubCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collections",
    )
    is_imported = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # social media
    site = models.URLField(max_length=50, blank=True, null=True, default=None)
    discord = models.CharField(max_length=50, blank=True, null=True, default=None)
    twitter = models.CharField(max_length=50, blank=True, null=True, default=None)
    instagram = models.CharField(max_length=50, blank=True, null=True, default=None)
    medium = models.CharField(max_length=50, blank=True, null=True, default=None)
    telegram = models.CharField(max_length=50, blank=True, null=True, default=None)

    objects = CollectionManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["address", "network"], name="unique collection"
            ),
        ]

    @property
    def avatar(self):
        if self.avatar_ipfs:
            return get_media_from_ipfs(self.avatar_ipfs)

    @property
    def cover(self):
        if self.cover_ipfs:
            return get_media_from_ipfs(self.cover_ipfs)

    @property
    def url(self):
        return self.short_url if self.short_url else self.id

    def __str__(self):
        return self.name

    @property
    def is_single(self):
        return self.standard == "ERC721"

    @property
    def game(self):
        if self.game_subcategory and self.game_subcategory.category:
            return self.game_subcategory.category.game

    @property
    def exchange(self):
        return CollectionExchange(collection=self)

    @property
    def block_difference(self):
        if self.status not in [Status.COMMITTED, Status.IMPORTING]:
            return None
        connection = RedisClient().connection
        last_block_number = connection.get(self.network.name)
        if not last_block_number:
            last_block_number = int(self.network.get_last_block())
            connection.set(self.network.name, last_block_number, ex=10)
        curent_block = connection.get(self.transfer_block_name)
        if last_block_number and curent_block:
            return int(last_block_number) - int(curent_block)

    @property
    def transfer_block_name(self) -> str:
        name = f"transfer_{self.network.name}_{self.network.wrap_in_checksum(self.address)}_{self.standard}"
        return name

    @property
    def email_fields(self):
        if self.game_subcategory:
            return {
                "user_name": self.game_subcategory.category.game.user.get_name(),
                "game_name": self.game_subcategory.category.game.name,
                "network": self.game_subcategory.category.game.network.name,
                "email": self.game_subcategory.category.game.email,
                "category_name": self.game_subcategory.category.name,
                "subcategory_name": self.game_subcategory.name,
                "collection_name": self.name,
                "collection_address": self.address,
                "contact_email": EmailConfig.get_admin_receiver(),
            }
        return {}

    def save_in_db(self, request, avatar, cover, game_subcategory=None):
        # TODO: move to controller
        self.name = request.data.get("name")
        self.symbol = request.data.get("symbol")
        self.address = request.data.get("address")
        network_name = request.query_params.get("network", config.DEFAULT_NETWORK)
        network = Network.objects.filter(name__icontains=network_name).first()
        self.creator_royalty = request.data.get("creator_royalty", 0)
        self.status = Status.PENDING
        self.network = network
        self.avatar_ipfs = avatar
        self.cover_ipfs = cover
        self.standard = request.data.get("standard") or request.data.get(
            "standart"
        )  # reverse compatibility
        self.description = request.data.get("description")
        short_url = request.data.get("short_url")
        if short_url:
            self.short_url = short_url
        if game_subcategory:
            self.game_subcategory = game_subcategory
        self.site = request.data.get("site")
        self.discord = request.data.get("discord")
        self.twitter = request.data.get("twitter")
        self.instagram = request.data.get("instagram")
        self.medium = request.data.get("medium")
        self.telegram = request.data.get("telegram")
        self.creator = request.user
        self.save()

    def create_token(
        self,
        creator_address,
        message,
    ):
        # TODO: move to exchanges
        if self.is_single:
            tx_types = ["uint256", "string", "uint256", "bytes"]
            return self.network.contract_call(
                method_type="write",
                contract_type="erc721main",
                address=self.address,
                gas_limit=TOKEN_MINT_GAS_LIMIT,
                nonce_username=creator_address,
                function_name="mint",
                input_params=message,
                input_type=tx_types,
            )
        tx_types = ["uint256", "uint256", "string", "unit256", "bytes"]
        return self.network.contract_call(
            method_type="write",
            contract_type="erc1155main",
            address=self.address,
            gas_limit=TOKEN_MINT_GAS_LIMIT,
            nonce_username=creator_address,
            function_name="mint",
            input_params=message,
            input_type=tx_types,
            send=False,
        )

    def get_contract(self):
        if self.is_single:
            return self.network.get_erc721main_contract(self.address)
        return self.network.get_erc1155main_contract(self.address)

    def get_active_id(self):
        headers = {"X-API-Key": config.MORALIS_API_KEY}
        response = requests.get(
            config.MORALIS_TRANSFER_URL.format(
                address=self.address, chain_name=self.network.moralis_slug
            ),
            headers=headers,
        )
        result = response.json().get("result")
        if result and result[0]:
            return result[0]["token_id"]

    def set_deploy_block(self):
        # try to get deploy block via etherscan api

        etherscan_blocks = []
        etherscan_actions = ["txlist", "txlistinternal"]
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
        }

        for action in etherscan_actions:
            response = requests.get(
                config.ETHERSCAN_TX_URL.format(
                    api_domain=self.network.api_domain,
                    action=action,
                    address=self.address,
                    key=self.network.api_key,
                ),
                headers=headers,
            )
            result = response.json().get("result")
            if result and result[0]:
                etherscan_blocks.append(result[0]["blockNumber"])
            time.sleep(1)

        if etherscan_blocks:
            self.deploy_block = min(etherscan_blocks)

        # if block not found, get first transfer block via moralis
        if not self.deploy_block:
            headers = {"X-API-Key": config.MORALIS_API_KEY}
            response = requests.get(
                config.MORALIS_TRANSFER_URL.format(
                    address=self.address, chain_name=self.network.moralis_slug
                ),
                headers=headers,
            )
            result = response.json().get("result")

            if result and result[0]:
                self.deploy_block = result[0]["block_number"]
        self.save(update_fields=("deploy_block",))


def validate_nonzero(value):
    if value < 0:
        raise ValidationError(
            "Quantity %(value)s is not allowed",
            params={"value": value},
        )


class TokenQuerySet(models.QuerySet):
    def committed(self):
        return self.filter(
            deleted=False, status=Status.COMMITTED, collection__status=Status.COMMITTED
        )

    def network(self, network):
        if network is None or network == "undefined":
            return self
        return self.filter(collection__network__name__icontains=network)

    def single(self):
        return self.filter(collection__standard="ERC721")

    def multiple(self):
        return self.filter(collection__standard="ERC1155")

    def game(self, game_name):
        if not game_name:
            return self
        return self.filter(collection__game_category__game__name__iexact=game_name)

    def game_category(self, game_category_name):
        if not game_category_name:
            return self
        return self.filter(collection__game_category__name__iexact=game_category_name)


class TokenManager(models.Manager):
    def get_queryset(self):
        return TokenQuerySet(self.model, using=self._db)

    def committed(self):
        """Return tokens with status committed"""
        return self.get_queryset().committed()

    def network(self, network):
        """Return token filtered by collection network name"""
        return self.get_queryset().network(network)

    def single(self):
        """Return token filtered by collection standard ERC721"""
        return self.get_queryset().single()

    def multiple(self):
        """Return token filtered by collection standard ERC1155"""
        return self.get_queryset().multiple()

    def game(self, game_name):
        """Return collections filtered by exists token with tag"""
        return self.get_queryset().game(game_name)

    def game_category(self, game_category_name):
        """Return collections filtered by exists token with tag"""
        return self.get_queryset().game_category(game_category_name)


class Token(models.Model):
    name = models.CharField(max_length=200)
    tx_hash = models.CharField(max_length=200, null=True, blank=True)
    ipfs = models.CharField(max_length=200, null=True, default=None)
    image = models.CharField(max_length=200, null=True, blank=True, default=None)
    animation_file = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        default=None,
    )
    format = models.CharField(max_length=12, null=True, default="image")
    total_supply = models.PositiveIntegerField(validators=[validate_nonzero])
    owners = models.ManyToManyField(
        "accounts.AdvUser", through="Ownership", null=True, related_name="owned_tokens"
    )
    creator = models.ForeignKey(
        "accounts.AdvUser",
        on_delete=models.PROTECT,
        related_name="created_tokens",
    )
    collection = models.ForeignKey(
        "Collection", on_delete=models.CASCADE, related_name="tokens"
    )
    internal_id = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN,
        blank=True,
        null=True,
        decimal_places=0,
    )

    description = models.TextField(blank=True, null=True)
    _properties = models.JSONField(blank=True, null=True, default=None)
    deleted = models.BooleanField(default=False)
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # tags = models.ManyToManyField("Tags", blank=True, null=True)
    category = models.ForeignKey(
        "Category", on_delete=models.SET_NULL, blank=True, null=True
    )
    is_favorite = models.BooleanField(default=False)
    digital_key = models.CharField(max_length=1000, blank=True, null=True, default=None)
    external_link = models.CharField(max_length=200, null=True, blank=True)
    mint_id = models.PositiveIntegerField(null=True, blank=True)

    objects = TokenManager()

    def __str__(self):
        return self.name

    @property
    def native_address(self):
        return self.collection.network.native_address.lower()

    @property
    def validator(self):
        return TokenValidator(token=self)

    @property
    def controller(self):
        return TokenController(token=self)

    @property
    def exchange(self):
        return TokenExchange(token=self)

    @property
    def is_single(self):
        return self.collection.standard == "ERC721"

    @property
    def properties(self) -> list:
        property_list = []
        if self._properties:
            connection = RedisClient().connection
            data = connection.get(f"perks_{self.collection.id}")
            if data:
                data = json.loads(data)
                for prop in self._properties.values():
                    prop["rarity"] = data[prop["trait_type"]]["perks"][
                        str(prop["trait_value"])
                    ]["rarity"]
                    property_list.append(prop)
            else:
                for prop in self._properties.values():
                    property_list.append(prop)
        return property_list

    @properties.setter
    def properties(self, value):
        if value:
            self._properties = value

    @property
    def media(self):
        if not self.image and not self.collection.is_imported:
            self.image = get_ipfs_by_hash(self.ipfs).get("image")
            self.save(update_fields=["image"])
        return self.image

    @property
    def animation(self):
        if (
            not self.animation_file
            and self.format != "image"
            and not self.collection.is_imported
        ):
            try:
                self.animation_file = get_ipfs_by_hash(self.ipfs).get("animation_url")
                self.save(update_fields=["animation_file"])
            except Exception as e:
                print(e)
        return self.animation_file

    @property
    def standard(self):
        return self.collection.standard

    @property
    def game(self):
        return self.collection.game

    @property
    def is_selling(self) -> Optional[bool]:
        return self.ownerships.filter(
            selling=True,
            price__isnull=False,
            currency__isnull=False,
        ).exists()

    @property
    def is_auc_selling(self) -> bool:
        return self.is_single and self.ownerships.filter(
            selling=True,
            minimal_bid__isnull=False,
            currency__isnull=False,
            _end_auction__isnull=True,
        )

    @property
    def is_timed_auc_selling(self) -> bool:
        now_ = timezone.now()
        return self.is_single and self.ownerships.filter(
            selling=True,
            minimal_bid__isnull=False,
            currency__isnull=False,
            _start_auction__lte=now_,
            _end_auction__gte=now_,
        )

    @property
    def minimal_bid(self):
        ownership = self.ownerships.filter(minimal_bid__isnull=False).first()
        if ownership:
            return ownership.minimal_bid

    @property
    def has_digital_key(self) -> bool:
        return bool(self.digital_key)

    def _parse_and_save_details(self, details):
        if isinstance(details, str):
            details = json.loads(details)
        data = {}
        if isinstance(details, dict):
            for key, value in details.items():
                data[key] = {"trait_type": key, "trait_value": value}
        elif isinstance(details, list):
            for trait in details:
                value = trait.pop("value", None)
                if value:
                    trait["trait_value"] = value
                data[trait["trait_type"]] = trait
        if data:
            setattr(self, "properties", data)

    def get_highest_bid(self) -> Optional["Bid"]:
        bids = self.bids.committed()
        if bids:
            return max(list(bids), key=lambda b: b.usd_amount)

    def _get_ownership_with_max_usd_price(
        self, is_max: bool = True
    ) -> Optional["Ownership"]:
        """return max price of ownerships (sort in usd)"""
        ownerships = self.ownerships.filter(selling=True)
        if ownerships:
            if is_max:
                return max(ownerships, key=lambda o: o.price_or_minimal_bid_usd or 0)
            return min(ownerships, key=lambda o: o.price_or_minimal_bid_usd or 2 ** 256)

    @property
    def currency(self):
        """return currency of ownerships with max price (sort in usd)"""
        ownership = self._get_ownership_with_max_usd_price(is_max=False)
        if ownership:
            return ownership.currency

    @property
    def price(self):
        """return price of ownerships with max price (sort in usd)"""
        ownership = self._get_ownership_with_max_usd_price(is_max=False)
        if ownership:
            return ownership.price_or_minimal_bid

    @property
    def usd_price(self):
        """return price of ownerships with max price (sort in usd)"""
        ownership = self._get_ownership_with_max_usd_price(is_max=False)
        if ownership:
            return ownership.price_or_minimal_bid_usd


class Ownership(models.Model):
    token = models.ForeignKey(
        "Token",
        related_name="ownerships",
        on_delete=models.CASCADE,
    )
    owner = models.ForeignKey("accounts.AdvUser", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(null=True, default=1)
    selling_quantity = models.PositiveIntegerField(null=True, default=0)
    selling = models.BooleanField(default=False)
    currency = models.ForeignKey(
        "rates.UsdRate",
        on_delete=models.PROTECT,
        null=True,
        default=None,
        blank=True,
    )
    price = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN,
        default=None,
        blank=True,
        null=True,
        decimal_places=18,
    )
    minimal_bid = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN,
        default=None,
        blank=True,
        null=True,
        decimal_places=18,
    )
    _start_auction = models.DateTimeField(blank=True, null=True, default=None)
    _end_auction = models.DateTimeField(blank=True, null=True, default=None)

    def __str__(self):
        return self.owner.get_name()

    @property
    def start_auction(self):
        if self._start_auction:
            return self._start_auction.timestamp()

    @start_auction.setter
    def start_auction(self, value):
        if value:
            self._start_auction = datetime.fromtimestamp(int(value))
        else:
            self._end_auction = None

    @property
    def end_auction(self):
        if self._end_auction:
            return self._end_auction.timestamp()

    @end_auction.setter
    def end_auction(self, value):
        if value:
            self._end_auction = datetime.fromtimestamp(int(value))
        else:
            self._end_auction = None

    @property
    def price_with_decimals(self):
        """Return price with decimals if instance has currency"""
        if self.price and self.currency:
            return int(self.price * self.currency.get_decimals)

    @property
    def minimal_bid_with_decimals(self) -> Optional[int]:
        """Return minimal_bid with decimals if instance has currency"""
        if self.minimal_bid and self.currency:
            return int(self.minimal_bid * self.currency.get_decimals)

    @property
    def price_or_minimal_bid(self) -> float:
        max_bid = self.token.get_highest_bid()
        if max_bid:
            return max_bid.amount
        return self.price or self.minimal_bid

    @property
    def price_or_minimal_bid_usd(self) -> float:
        if self.price_or_minimal_bid and self.currency:
            return self.price_or_minimal_bid * self.currency.rate


class Category(models.Model):
    name = models.CharField(max_length=30, unique=True)
    image = models.CharField(max_length=200, blank=True, null=True, default=None)
    banner = models.CharField(max_length=200, blank=True, null=True, default=None)
    description = models.CharField(max_length=500, blank=True, null=True, default=None)

    def __str__(self):
        return self.name

    @property
    def ipfs_image(self):
        if self.image:
            return get_media_from_ipfs(self.image)

    @property
    def ipfs_banner(self):
        if self.banner:
            return get_media_from_ipfs(self.banner)

    class Meta:
        verbose_name_plural = "Categories"


class Tags(models.Model):
    category = models.ForeignKey(
        "Category",
        on_delete=models.CASCADE,
        related_name="tags",
        null=True,
        blank=True,
        default=None,
    )
    name = models.CharField(max_length=30, unique=True)
    image = models.CharField(max_length=200, blank=True, null=True, default=None)
    banner = models.CharField(max_length=200, blank=True, null=True, default=None)
    description = models.TextField(blank=True, null=True, default=None)

    @property
    def ipfs_image(self):
        if self.image:
            return get_media_from_ipfs(self.image)

    @property
    def ipfs_banner(self):
        if self.banner:
            return get_media_from_ipfs(self.banner)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Tags"


class BidQuerySet(models.QuerySet):
    def committed(self):
        return self.filter(state=Status.COMMITTED)


class BidManager(models.Manager):
    def get_queryset(self):
        return BidQuerySet(self.model, using=self._db)

    def committed(self):
        """Return bids with status committed"""
        return self.get_queryset().committed()


class Bid(models.Model):
    token = models.ForeignKey("Token", on_delete=models.CASCADE, related_name="bids")
    quantity = models.PositiveIntegerField(null=True)
    user = models.ForeignKey(
        "accounts.AdvUser", on_delete=models.PROTECT, related_name="bids"
    )
    amount = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN,
        decimal_places=18,
        default=None,
        blank=True,
        null=True,
    )
    currency = models.ForeignKey(
        "rates.UsdRate", on_delete=models.PROTECT, null=True, blank=True, default=None
    )
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(
        max_length=50, choices=Status.choices, default=Status.PENDING
    )

    objects = BidManager()

    def __str__(self):
        return f"{self.token} - {self.user}"

    @property
    def usd_amount(self):
        return self.amount * self.currency.rate


class TransactionTracker(models.Model):
    tx_hash = models.CharField(max_length=200, null=True, blank=True)
    token = models.ForeignKey(
        "Token", on_delete=models.CASCADE, null=True, blank=True, default=None
    )
    ownership = models.ForeignKey(
        "Ownership", on_delete=models.CASCADE, null=True, blank=True, default=None
    )
    bid = models.ForeignKey(
        "Bid", on_delete=models.CASCADE, null=True, blank=True, default=None
    )
    amount = models.PositiveSmallIntegerField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    auction = models.BooleanField(null=True, blank=True, default=False)

    def __str__(self):
        return f"Tracker hash - {self.tx_hash}"

    @property
    def item(self):
        if self.token:
            return self.token
        return self.ownership


class ViewsTracker(models.Model):
    user_id = models.IntegerField(null=True)
    token = models.ForeignKey("Token", on_delete=models.CASCADE, related_name="views")
    created_at = models.DateTimeField(auto_now_add=True)
