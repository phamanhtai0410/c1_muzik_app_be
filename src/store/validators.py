from typing import TYPE_CHECKING, Dict, Optional

from django.apps import apps

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from src.accounts.models import AdvUser
    from src.networks.models import Network
    from src.store.models import Collection, Token


class TokenValidator:
    """
    Builder of validations for token.

    All validator methods will be return self!
    You can call validator methods and after this call 'errors'.
    This retrun dict of errors or None if all validations is complete.

    Important: keys of errors should not be repeated!

    For example:
    errors = Token(token).is_complete().is_owner(user).errors
    # TODO: mb use APIException?
    """

    def __init__(self, token: "Token") -> None:
        self.token = token
        self._errors = {}

    @property
    def errors(self) -> Optional[dict]:
        return self._errors or None

    def is_committed(self) -> "TokenValidator":
        """Check token status is committed."""
        if self.token.status != "Committed":
            self._errors["status_error"] = f"Token status is {self.token.status}"
        return self

    def is_owner(self, user: "AdvUser") -> "TokenValidator":
        """Check user is owner of token."""
        if not self.token.ownerships.filter(owner=user).exists():
            self._errors["owner_error"] = f"token {self.token} doesn't belong to {user}"
        return self

    def is_removable_from_sale(self) -> "TokenValidator":
        """Check token has bids"""
        if self.token.bids.committed().exists():
            self._errors["remove_from_sale_error"] = f"token {self.token} has bids"
        return self

    def is_seller(self, user: "AdvUser") -> "TokenValidator":
        """Check user is selling token."""
        if not self.token.ownerships.filter(owner=user, selling=True).exists():
            self._errors["seller_error"] = f"{user} does not sell this token"
        return self

    def is_selling(self) -> "TokenValidator":
        """Check token is selling."""
        if not self.token.ownerships.filter(selling=True).exists():
            self._errors["selling_error"] = "token not selling"
        return self

    def is_valid_amount_for_buy(self, amount: int) -> "TokenValidator":
        """
        Valid amount for 721 is 0.
        Valid amount for 1155 > 0.
        """
        if self.token.is_single and amount != 0:
            self._errors["wrong_buy_amount"] = "amount for 721 should be equal 0"
        elif not self.token.is_single and amount == 0:
            self._errors["wrong_buy_amount"] = "amount for 1155 should be more than 0"
        return self

    def is_name_unique_for_network(
        self,
        name: str,
        network: "Network",
    ) -> "TokenValidator":
        token_model = apps.get_model("store", "Token")
        if token_model.objects.filter(name=name, collection__network=network).exists():
            self._errors["unique_name"] = "this token name is occupied"
        return self

    def is_valid_total_supply(self, total_supply: int) -> "TokenValidator":
        # TODO: refactor on more understandable
        if self.token.is_single and total_supply != 1:
            self._errors["total_supply"] = "721 token total supply is not valid value"
        elif not self.token.is_single and total_supply < 1:
            self._errors["total_supply"] = "1155 token total supply is not valid value"
        return self

    def is_valid_data_for_sell(self, minimal_bid: float) -> "TokenValidator":
        # TODO: refactor on more understandable
        if not self.token.is_single and minimal_bid:
            self._errors["minimal_bid"] = "1155 token cannot be put on auction"
        return self

    def is_valid_fee_address(self, fee_address: str) -> "TokenValidator":
        if fee_address.lower() != self.token.native_address:
            self._errors["fee_address"] = "invalid fee address"
        return self

    def is_approved(self, user: "AdvUser") -> "TokenValidator":
        if not self.token.controller.check_is_approved(user):
            self._errors["approve"] = "Not approved, can't set for sale"
        return self

    def has_bid(self) -> "TokenValidator":
        if (
            self.token.is_auc_selling or self.token.is_timed_auc_selling
        ) and self.token.get_highest_bid():
            self._errors["auction"] = "The token is put up for auction and has a bid"
        return self

    def check_highest_bid(self, user: "AdvUser", amount: int) -> "TokenValidator":
        if (
            self.token.get_highest_bid()
            and self.token.get_highest_bid().amount > amount
        ):
            self._errors["bid"] = "Your bid is too low"

    def check_validate_bid(self, user: "AdvUser", amount: int) -> "TokenValidator":
        """Check bid data is valid (only for signle token)"""
        network = self.token.currency.network

        user_balance = network.contract_call(
            method_type="read",
            contract_type="token",
            address=self.token.currency.address,
            function_name="balanceOf",
            input_params=(network.wrap_in_checksum(user.username),),
            input_type=("address",),
            output_types=("uint256",),
        )

        allowance = network.contract_call(
            method_type="read",
            contract_type="token",
            address=self.token.currency.address,
            function_name="allowance",
            input_params=(
                network.wrap_in_checksum(user.username),
                network.exchange_address,
            ),
            input_type=("address", "address"),
            output_types=("uint256",),
        )

        if user_balance < amount * self.token.currency.get_decimals:
            self._errors["bidding_balance"] = "Your bidding balance is too small"

        if allowance < amount * self.token.currency.get_decimals:
            self._errors["allowance"] = "Your allowance is too small"

        return self

    def is_cover_required(
        self, media_files: "Dict[str, UploadedFile]", media_type: Optional[str]
    ) -> "TokenValidator":
        cover = media_files.get("cover")

        cover_required = True
        if media_type and media_type == "image":
            cover_required = False

        if not cover and cover_required:
            self._errors["media"] = "Cover is required for non-static media files"
        elif cover and not cover_required:
            self._errors["cover"] = "Covers are prohibited for media with image type"

        return self

    def is_valid_media(self, media_type: Optional[str]) -> "TokenValidator":
        if not media_type:
            self._errors["media"] = "Media file of this type is not recognized"

        return self


class CollectionValidator:
    """
    Builder of validations for collection.

    All validator methods will be return self!
    You can call validator methods and after this call 'errors'.
    This retrun dict of errors or None if all validations is complete.

    Important: keys of errors should not be repeated!
    """

    def __init__(self, collection: "Collection" = None) -> None:
        self.collection = collection
        self._errors = {}

    @property
    def errors(self) -> Optional[dict]:
        return self._errors or None

    def is_name_unique_for_network(
        self,
        name: str,
        network: "Network",
    ) -> "CollectionValidator":
        collection_model = apps.get_model("store", "Collection")
        if collection_model.objects.filter(name__iexact=name, network=network).exists():
            self._errors["unique_name"] = "this collection name is occupied"
        return self

    def is_symbol_unique_for_network(
        self,
        symbol: str,
        network: "Network",
    ) -> "CollectionValidator":
        collection_model = apps.get_model("store", "Collection")
        if collection_model.objects.filter(symbol=symbol, network=network).exists():
            self._errors["unique_symbol"] = "this collection symbol is occupied"
        return self

    def is_correct_standard(self, standard: str) -> "CollectionValidator":
        """if short_url is an empty string, it is unique"""
        if standard not in ["ERC721", "ERC1155"]:
            self._errors["standard_error"] = "standard should be 'ERC721' or 'ERC1155'"
        return self

    def is_short_url_unique(self, short_url: str) -> "CollectionValidator":
        """if short_url is an empty string, it is unique"""
        collection_model = apps.get_model("store", "Collection")
        if short_url and collection_model.objects.filter(short_url=short_url).exists():
            self._errors["unique_short_url"] = "this collection short_url is occupied"
        return self

    def is_game_add_valid(self, game_subcategory, user):
        if game_subcategory.category.game.user != user:
            self._errors["access error"] = "You are not the owner of this game"
        return self
