from django.db import models
from django.db.models import Exists, OuterRef

from src.store.models import Collection
from src.support.models import EmailConfig
from src.utilities import get_media_from_ipfs

from .signals_definition import game_approved
from .validator import Validator


class GameCompany(models.Model):
    """
    Model representing listed game
    """

    name = models.CharField(max_length=100)
    user = models.ForeignKey(
        "accounts.AdvUser", on_delete=models.CASCADE, related_name="games"
    )
    network = models.ForeignKey(
        "networks.Network",
        on_delete=models.CASCADE,
        related_name="games",
    )
    email = models.EmailField(max_length=100)
    avatar_ipfs = models.CharField(max_length=100, null=True)
    banner_ipfs = models.CharField(max_length=100, null=True)
    background_color = models.CharField(max_length=10, null=True, blank=True)
    description = models.CharField(max_length=1000, null=True, blank=True)
    is_approved = models.BooleanField(null=True)
    validating_result = models.TextField(null=True, blank=True)
    # social medias
    website = models.CharField(max_length=200, default=None, null=True, blank=True)
    twitter = models.CharField(max_length=80, default=None, null=True, blank=True)
    instagram = models.CharField(max_length=80, default=None, null=True, blank=True)
    telegram = models.CharField(max_length=80, default=None, null=True, blank=True)
    discord = models.CharField(max_length=80, default=None, null=True, blank=True)
    medium = models.CharField(max_length=80, default=None, null=True, blank=True)
    facebook = models.CharField(max_length=80, default=None, null=True, blank=True)
    whitepaper_link = models.CharField(
        max_length=200, default=None, null=True, blank=True
    )

    @property
    def avatar(self):
        return get_media_from_ipfs(self.avatar_ipfs)

    @property
    def banner(self):
        return get_media_from_ipfs(self.banner_ipfs)

    @property
    def email_fields(self):
        return {
            "user_name": self.user.get_name(),
            "game_name": self.name,
            "network": self.network.name,
            "email": self.email,
            "contact_email": EmailConfig.get_admin_receiver(),
        }

    @property
    def addresses(self):
        address_list = list(
            set(
                list(
                    self.categories.all().values_list(
                        "subcategories__collections__address", flat=True
                    )
                )
            )
        )
        if None in address_list:
            address_list.remove(None)
        return address_list

    def __str__(self):
        return self.name

    def validate_contracts(self):
        # validate contracts before approve
        validator = Validator(self)
        validator.validate()

    def parse_collections(self):
        # get name and symbol for each collection in game, if exists
        network_id = self.network.id
        for address in self.addresses:
            name, symbol = Validator.fetch_collection_info(address, network_id)
            collection = Collection.objects.get(network_id=network_id, address=address)
            collection.name = name
            collection.symbol = symbol
            collection.save(update_fields=("name", "symbol"))

    def delete_empty_nested_models(self):
        # delete empty nested models
        GameSubCategory.objects.filter(category__game=self).filter(
            ~Exists(Collection.objects.filter(game_subcategory=OuterRef("pk")))
        ).delete()
        GameCategory.objects.filter(game=self).filter(
            ~Exists(GameSubCategory.objects.filter(category=OuterRef("pk")))
        ).delete()
        if not self.categories.exists():
            self.validating_result = "All collections are invalid"
            self.is_approved = False
            print("sending approve")
            game_approved.send(
                sender=self.__class__, instance=self, approved=self.is_approved
            )
        else:
            self.validating_result = "valid"
        self.save()

    def set_deploy_blocks(self):
        collections = Collection.objects.filter(game_subcategory__category__game=self)
        for collection in collections:
            collection.set_deploy_block()

    class Meta:
        verbose_name_plural = "Game Companies"


class GameCategory(models.Model):
    """
    model representing game categories
    """

    game = models.ForeignKey(
        "GameCompany", on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=100)
    avatar_ipfs = models.CharField(max_length=100, null=True, blank=True)
    is_approved = models.BooleanField(null=True)

    def __str__(self):
        return f"{self.game.name} {self.name}"

    @property
    def avatar(self):
        return get_media_from_ipfs(self.avatar_ipfs)

    @property
    def address_list(self):
        address_list = self.subcategories.all().values_list(
            "collections__address", flat=True
        )
        address_objects = [{"address": address} for address in address_list]
        return address_objects

    @property
    def addresses(self):
        # return all category addresses formatted for admin panel
        address_list = list(
            set(
                list(
                    self.subcategories.all().values_list(
                        "collections__address", flat=True
                    )
                )
            )
        )
        if None in address_list:
            address_list.remove(None)
        return (
            str(address_list)
            .replace("[", "")
            .replace("]", "")
            .replace("'", "")
            .replace('"', "")
            .replace(",", "\n")
        )

    @property
    def email_fields(self):
        return {
            "user_name": self.game.user.get_name(),
            "game_name": self.game.name,
            "network": self.game.network.name,
            "email": self.game.email,
            "category_name": self.name,
            "contact_email": EmailConfig.get_admin_receiver(),
        }

    class Meta:
        verbose_name_plural = "Categories"
        ordering = [
            "id",
        ]


class GameSubCategory(models.Model):
    """
    model representing game categories
    """

    category = models.ForeignKey(
        "GameCategory", on_delete=models.CASCADE, related_name="subcategories"
    )
    name = models.CharField(max_length=100)
    avatar_ipfs = models.CharField(max_length=100, null=True, blank=True)
    is_approved = models.BooleanField(null=True)

    def __str__(self):
        return f"{self.category.game.name} {self.category.name} {self.name}"

    @property
    def game(self):
        return self.category.game

    @property
    def avatar(self):
        return get_media_from_ipfs(self.avatar_ipfs)

    @property
    def address_list(self):
        address_list = self.collections.all().values_list("address", flat=True)
        address_objects = [{"address": address} for address in address_list]
        return address_objects

    @property
    def addresses(self):
        # return all category addresses formatted for admin panel
        return (
            str(list(self.collections.values_list("address", flat=True)))
            .replace("[", "")
            .replace("]", "")
            .replace("'", "")
            .replace('"', "")
            .replace(",", "\n")
        )

    @property
    def email_fields(self):
        return {
            "user_name": self.category.game.user.get_name(),
            "game_name": self.category.game.name,
            "network": self.category.game.network.name,
            "email": self.category.game.email,
            "category_name": self.category.name,
            "subcategory_name": self.name,
            "contact_email": EmailConfig.get_admin_receiver(),
        }

    class Meta:
        ordering = [
            "id",
        ]
        verbose_name_plural = "Sub Categories"


class DefaultGameAvatar(models.Model):
    image = models.CharField(max_length=200, blank=True, null=True, default=None)

    @property
    def ipfs_image(self):
        return get_media_from_ipfs(self.image)


class DefaultGameBanner(models.Model):
    image = models.CharField(max_length=200, blank=True, null=True, default=None)

    @property
    def ipfs_image(self):
        return get_media_from_ipfs(self.image)


class GameCollection(Collection):
    class Meta:
        proxy = True
