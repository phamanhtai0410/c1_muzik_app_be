import json
import logging
import operator
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from src.accounts.models import AdvUser
from src.accounts.serializers import UserFollowSerializer
from src.activity.models import TokenHistory, UserAction
from src.store.models import Bid, Category, Collection, Ownership, Token
from src.store.serializers import CompositeCollectionSerializer, TokenSerializer


class SearchABC(ABC):
    @abstractmethod
    def initial(self):
        """initial items and serializer"""
        ...

    def remove_unused_kwargs(self, kwargs):
        kwargs.pop("page", None)
        kwargs.pop("items_per_page", None)

    def serialize(self, data):
        return self.serializer(
            data,
            context={"user": self.user},
            many=True,
        ).data

    def parse(self, **kwargs):
        self.initial()
        self.remove_unused_kwargs(kwargs)

        self.currency_symbol = kwargs.get("currency", [None])[0]
        self.user = kwargs.pop("current_user", None)
        order_by = kwargs.pop(
            "order_by",
            [
                "-created_at",
            ],
        )

        for method, value in kwargs.items():
            try:
                getattr(self, method)(value)
            except AttributeError as e:
                logging.warning(e)
            except Exception as e:
                logging.error(e)

        if order_by and order_by[0] and hasattr(self, "order_by"):
            self.order_by(order_by)

        return self.items


class SearchToken(SearchABC):
    def initial(self):
        self.items = Token.objects.committed()
        self.serializer = TokenSerializer

    def network(self, network):
        if network and network[0]:
            if not network[0].lower() == "undefined":
                networks = network[0].split(",")
                self.items = self.items.filter(collection__network__name__in=networks)

    def tags(self, tags):
        if tags and tags[0]:
            tags = tags[0].split(",")
            self.items = self.items.filter(tags__id__in=tags).distinct()

    def categories(self, categories):
        if categories and categories[0]:
            categories = categories[0].split(",")
            categories = [int(c) for c in categories]
            self.items = self.items.filter(category__id__in=categories).distinct()

    def text(self, words):
        if words and words[0]:
            words = words[0].split(" ")
            for word in words:
                self.items = self.items.filter(name__icontains=word)

    def stats(self, stats):
        if stats and stats[0]:
            stats = json.loads(stats[0])
            for stat, value in stats.items():
                min_data = value.get("min")
                max_data = value.get("max")
                stat_filters = {}
                if min_data:
                    stat_filters[f"_stats__{stat}__value__gte"] = float(min_data)
                if max_data:
                    stat_filters[f"_stats__{stat}__value__lte"] = float(max_data)
                self.items = self.items.filter(**stat_filters)

    def rankings(self, rankings):
        if rankings and rankings[0]:
            rankings = json.loads(rankings[0])
            for rank, value in rankings.items():
                min_data = value.get("min")
                max_data = value.get("max")
                rank_filters = {}
                if min_data:
                    rank_filters[f"_rankings__{rank}__value__gte"] = float(min_data)
                if max_data:
                    rank_filters[f"_rankings__{rank}__value__lte"] = float(max_data)
                self.items = self.items.filter(**rank_filters)

    def on_any_sale(self, _):
        self.items = self.items.filter(
            Exists(
                Ownership.objects.filter(
                    token__id=OuterRef("id"),
                    selling=True,
                )
            )
        ).distinct()

    def on_any_sale_by(self, _user):
        try:
            user = AdvUser.objects.get_by_custom_url(_user[0])
            self.items = self.items.filter(
                ownerships__owner=user,
                ownerships__selling=True,
            )
        except ObjectDoesNotExist:
            return

    def properties(self, properties):
        if properties and properties[0]:
            props = json.loads(properties[0])
            for prop, value in props.items():
                if value:
                    props_filter = {f"_properties__{prop}__trait_value__in": value}
                    self.items = self.items.filter(**props_filter)

    def is_verified(self, is_verified):
        if is_verified is not None:
            is_verified = is_verified[0]
            is_verified = is_verified.lower() == "true"
            self.items = self.items.filter(owners__is_verificated=is_verified)

    def _price_filter_tokens(self, price, type_):
        relate = operator.ge
        if type_ == "max_price":
            relate = operator.le
        price = str(price[0]).replace(".", "") if price and price[0] else ""
        if price.isdigit():
            self.on_any_sale("")
            filter_price = Decimal(price)

            price_field = "usd_price" if not self.currency_symbol else "price"
            token_ids = [
                token.id
                for token in self.items
                if relate(
                    getattr(token, price_field) if getattr(token, price_field) else 0,
                    filter_price,
                )
            ]
            self.items = Token.objects.committed().filter(id__in=token_ids)

    def min_price(self, price):
        self._price_filter_tokens(price, "min_price")

    def max_price(self, price):
        self._price_filter_tokens(price, "max_price")

    def standard(self, standard):
        if standard and standard[0]:
            standard = standard[0]
            if standard in ["ERC721", "ERC1155"]:
                self.items = self.items.filter(collection__standard=standard)

    def collections(self, collections):
        if collections and collections[0]:
            collections = collections[0].split(",")
            collection_ids = [col for col in collections if str(col).isdigit()]
            collection_short = [col for col in collections if col not in collection_ids]
            self.items = self.items.filter(
                Q(collection__id__in=collection_ids)
                | Q(collection__short_url__in=collection_short)
            )

    def related_collections(self, collections):
        if collections and collections[0]:
            collections = collections[0].split(",")
            collection_ids = [col for col in collections if str(col).isdigit()]
            collection_short = [col for col in collections if col not in collection_ids]
            subcategories = list(
                set(
                    list(
                        Collection.objects.filter(
                            Q(id__in=collection_ids) | Q(short_url__in=collection_short)
                        ).values_list("game_subcategory__id", flat=True)
                    )
                )
            )
            if None in subcategories:
                subcategories.remove(None)
            self.items = self.items.filter(
                collection__game_subcategory__in=subcategories
            )

    def owner(self, owner):
        if owner:
            try:
                owner = AdvUser.objects.get_by_custom_url(owner[0])
                self.items = self.items.filter(owners=owner)
            except ObjectDoesNotExist:
                self.items = Token.objects.none()

    def creator(self, creator):
        if creator:
            try:
                creator = AdvUser.objects.get_by_custom_url(creator[0])
                self.items = self.items.filter(creator=creator).order_by("-id")
            except ObjectDoesNotExist:
                self.items = Token.objects.none()

    def currency(self, currency):
        if currency and currency[0]:
            currencies = currency[0].split(",")
            self.items = self.items.filter(
                Exists(
                    Ownership.objects.filter(
                        token__id=OuterRef("id"),
                        currency__symbol__in=currencies,
                    )
                )
            )

    def on_sale(self, on_sale):
        if on_sale and on_sale[0]:
            filter = "filter" if on_sale[0].lower() == "true" else "exclude"
            self.items = getattr(self.items, filter)(
                Exists(
                    Ownership.objects.filter(
                        token__id=OuterRef("id"),
                        selling=True,
                        price__isnull=False,
                    )
                )
            )

    def on_auc_sale(self, on_sale):
        if on_sale and on_sale[0]:
            filter = "filter" if on_sale[0].lower() == "true" else "exclude"
            self.items = getattr(self.items, filter)(
                Exists(
                    Ownership.objects.filter(
                        token__id=OuterRef("id"),
                        selling=True,
                        price__isnull=True,
                        minimal_bid__isnull=False,
                    )
                )
            )

    def on_timed_auc_sale(self, on_sale):
        if on_sale and on_sale[0] != "":
            filter = "filter" if on_sale[0].lower() == "true" else "exclude"
            self.items = getattr(self.items, filter)(
                Exists(
                    Ownership.objects.filter(
                        token__id=OuterRef("id"),
                        selling=True,
                        price__isnull=True,
                        minimal_bid__isnull=False,
                        _start_auction__lte=timezone.now(),
                        _end_auction__gte=timezone.now(),
                    )
                )
            )

    def has_bids(self, has_bids):
        if has_bids:
            filter = "filter" if has_bids[0].lower() == "true" else "exclude"
            self.items = getattr(self.items, filter)(
                Exists(Bid.objects.filter(token__id=OuterRef("id")))
            )

    def sold_by(self, user_):
        if user_ is not None:
            try:
                user = AdvUser.objects.get_by_custom_url(user_[0])
            except AdvUser.DoesNotExist:
                return
            self.items = self.items.filter(
                Exists(
                    TokenHistory.objects.filter(
                        old_owner=user,
                        method="Buy",
                        token__id=OuterRef("id"),
                    )
                )
            )

    def liked_by(self, user_):
        if user_ is not None:
            try:
                user = AdvUser.objects.get_by_custom_url(user_[0])
            except AdvUser.DoesNotExist:
                return
            else:
                token_ids = list(
                    UserAction.objects.filter(
                        method="like",
                        user=user,
                    ).values_list("token_id", flat=True)
                )
                self.items = self.items.filter(id__in=token_ids)

    def bids_by(self, user_):
        if user_ is not None:
            try:
                user = AdvUser.objects.get_by_custom_url(user_[0])
            except AdvUser.DoesNotExist:
                return
            else:
                self.items = self.items.filter(
                    Exists(
                        Bid.objects.filter(
                            token__id=OuterRef("id"),
                            user=user,
                        )
                    )
                )

    def game(self, game):
        if game and game[0] is not None:
            if int(game[0]) == 0:
                self.items = self.items.filter(
                    collection__game_subcategory__category__game__isnull=False
                )
            else:
                self.items = self.items.filter(
                    collection__game_subcategory__category__game__id=game[0]
                )

    def order_by_price(self, token, reverse=False):
        default_value = 0 if reverse else float("inf")
        token_price = (
            token.get_highest_bid().usd_amount
            if token.get_highest_bid()
            else token.usd_price
        )
        return token_price or default_value

    def order_by_likes(self, token, reverse=False):
        return token.likes.count()

    def order_by_created_at(self, token, reverse=False):
        return token.created_at

    def order_by_views(self, token, reverse=False):
        return token.views.count()

    def order_by_sale(self, token, reverse=False):
        history = token.history.filter(method="Buy").order_by("date").last()
        if history and history.date:
            return history.date
        return timezone.make_aware(datetime.fromtimestamp(0))

    def order_by_transfer(self, token, reverse=False):
        history = token.history.filter(method="Transfer").order_by("date").last()
        if history and history.date:
            return history.date
        return timezone.make_aware(datetime.fromtimestamp(0))

    def order_by_auction_end(self, token, reverse=False):
        default_value = timezone.make_aware(datetime.fromtimestamp(0))
        if token.is_timed_auc_selling:
            return token._end_auction
        return default_value

    def order_by_last_sale(self, token, reverse=False):
        history = token.history.filter(method="Buy").order_by("date").last()
        if history and history.price:
            return history.price
        return 0

    def order_by(self, order_by):
        tokens = list(self.items)
        reverse = False
        if order_by is not None:
            order_by = order_by[0]
            if order_by.startswith("-"):
                order_by = order_by[1:]
                reverse = True

        if hasattr(self, f"order_by_{order_by}"):
            try:
                tokens = sorted(
                    tokens,
                    key=lambda token: getattr(self, f"order_by_{order_by}")(
                        token, reverse
                    ),
                    reverse=reverse,
                )
            except AttributeError as e:
                logging.error(e)
        else:
            logging.warning(f"Unknown token sort method {order_by}")

        self.items = tokens


class SearchCollection(SearchABC):
    def initial(self):
        self.items = Collection.objects.committed()
        self.serializer = CompositeCollectionSerializer

    def standard(self, standard):
        if standard and standard[0]:
            standard = standard[0]
            if standard in ["ERC721", "ERC1155"]:
                self.items = self.items.filter(standard=standard)

    def tags(self, tags):
        if tags and tags[0]:
            tags = tags[0].split(",")
            self.items = self.items.filter(
                Exists(
                    Token.objects.committed().filter(
                        tags__name__in=tags,
                        collection__id=OuterRef("id"),
                    )
                )
            )

    def creator(self, user):
        if user and user[0]:
            try:
                user = AdvUser.objects.get_by_custom_url(user[0])
                self.items = self.items.filter(creator=user)
            except ObjectDoesNotExist:
                self.items = Collection.objects.none()

    def text(self, words):
        if words and words[0]:
            words = words[0].split(" ")
            for word in words:
                self.items = self.items.filter(name__icontains=word)

    def network(self, network):
        if network and network[0]:
            if not network[0].lower() == "undefined":
                networks = network[0].split(",")
                self.items = self.items.filter(network__name__in=networks)

    def category(self, category):
        if category and category[0]:
            try:
                cat = Category.objects.get(id=category[0])
                self.items = Collection.objects.category(cat.name)
            except ObjectDoesNotExist:
                self.items = Collection.objects.none()

    def game(self, game):
        if game and game[0] is not None:
            if int(game[0]) == 0:
                self.items = self.items.filter(
                    game_subcategory__category__game__isnull=False
                )
            else:
                self.items = self.items.filter(
                    game_subcategory__category__game__id=game[0]
                )

    def related_collections(self, collections):
        if collections and collections[0]:
            collections = collections[0].split(",")
            collection_ids = [col for col in collections if str(col).isdigit()]
            collection_short = [col for col in collections if col not in collection_ids]
            subcategories = list(
                set(
                    list(
                        Collection.objects.filter(
                            Q(id__in=collection_ids) | Q(short_url__in=collection_short)
                        ).values_list("game_subcategory__id", flat=True)
                    )
                )
            )
            if None in subcategories:
                subcategories.remove(None)
            self.items = self.items.filter(game_subcategory__in=subcategories)

    def order_by_name(self, collection, reverse=False):
        return collection.name

    def order_by(self, order_by):
        collections = list(self.items)
        reverse = False
        if order_by is not None:
            order_by = order_by[0]
            if order_by.startswith("-"):
                order_by = order_by[1:]
                reverse = True

        if hasattr(self, f"order_by_{order_by}"):
            try:
                collections = sorted(
                    collections,
                    key=lambda collection: getattr(self, f"order_by_{order_by}")(
                        collection, reverse
                    ),
                    reverse=reverse,
                )
            except AttributeError as e:
                logging.error(e)
        else:
            logging.warning(f"Unknown token sort method {order_by}")

        self.items = collections


class SearchUser(SearchABC):
    def initial(self):
        self.items = AdvUser.objects.all()
        self.serializer = UserFollowSerializer

    def text(self, words):
        if words and words[0]:
            words = words[0].split(" ")
            for word in words:
                self.items = self.items.filter(display_name__icontains=word)

    def verificated(self, verificated):
        self.items = self.items.filter(is_verificated=verificated[0].lower() == "true")

    def order_by_created(self, reverse):
        return self.items.order_by(f"{reverse}id")

    def order_by_followers(self, reverse):
        return self.items.annotate(follow_count=Count("following")).order_by(
            f"{reverse}follow_count"
        )

    def order_by_tokens_created(self, reverse):
        return self.items.annotate(creators=Count("token_creator")).order_by(
            f"{reverse}creators"
        )

    def order_by(self, order_by):
        reverse = "-" if order_by[0] == "-" else ""
        order_by = order_by.strip("-")
        try:
            users = getattr(self, f"order_by_{order_by}")(reverse)
        except AttributeError:
            logging.warning(f"Unknown token sort method {order_by}")
        self.items = users


Search = {
    "token": SearchToken(),
    "collection": SearchCollection(),
    "user": SearchUser(),
}
