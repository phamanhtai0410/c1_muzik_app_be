from typing import TYPE_CHECKING, Optional

from django.apps import apps
from web3.exceptions import ContractLogicError

from src.settings import config
from src.store.models import Collection, Status

if TYPE_CHECKING:
    from .models import GameCompany


class Validator:
    """
    validate all contract methods of ERC721 and ERC1155 contracts (including Metadata methods)
    At least one minted token is mandatory.
    """

    def __init__(self, game: "GameCompany") -> None:
        self.collections = Collection.objects.filter(
            game_subcategory__category__game=game
        )
        self._errors = ""

    @property
    def errors(self):
        return self._errors

    def validate(self):
        for collection in self.collections.filter(status=Status.PENDING):
            active_id = collection.get_active_id()
            if not active_id:
                self._errors += f"{collection.address}: No active tokens \n"
            else:
                active_id = int(active_id)
                self.validate_metadata(collection, active_id)
                self.validate_allowance(collection)
                self.validate_balance_and_owner(collection, active_id)
            if not self._errors:
                collection.save(update_fields=("standard",))
            else:
                collection.delete()
                self._errors = ""

    def validate_metadata(self, collection, active_id):
        contract = collection.network.get_erc721main_contract(
            address=collection.address
        )
        try:
            contract.functions.tokenURI(active_id).call()
            collection.standard = "ERC721"
        except (ContractLogicError, ValueError):
            contract = collection.network.get_erc1155main_contract(
                address=collection.address
            )
            try:
                contract.functions.uri(active_id).call()
                collection.standard = "ERC1155"
            except (ContractLogicError, ValueError):
                self._errors += f"{collection.address}: Invalid metadata methods \n"

    def validate_allowance(self, collection):
        contract = collection.network.get_erc721main_contract(
            address=collection.address
        )
        try:
            contract.functions.isApprovedForAll(
                config.SIGNER_ADDRESS, config.SIGNER_ADDRESS
            ).call()
        except (ContractLogicError, ValueError):
            self._errors += f"{collection.address}: Invalid allowance mechanics \n"

    def validate_balance_and_owner(self, collection, active_id):
        if collection.standard == "ERC1155":
            contract = collection.network.get_erc1155main_contract(
                address=collection.address
            )
            try:
                contract.functions.balanceOf(config.SIGNER_ADDRESS, active_id).call()
            except (ContractLogicError, ValueError):
                self._errors += f"{collection.address}: Invalid balance mechanics \n"
        if collection.standard == "ERC721":
            contract = collection.network.get_erc721main_contract(
                address=collection.address
            )
            try:
                contract.functions.balanceOf(config.SIGNER_ADDRESS).call()
            except (ContractLogicError, ValueError):
                self._errors += f"{collection.address}: Invalid balance mechanics \n"
            try:
                contract.functions.ownerOf(active_id).call()
            except (ContractLogicError, ValueError):
                self._errors += (
                    f"{collection.address}: Invalid token owners mechanics \n"
                )

    @staticmethod
    def fetch_collection_info(
        contract_address: str, network_id: int
    ) -> (str, Optional[str]):
        network_model = apps.get_model("networks", "Network")
        network = network_model.objects.get(id=network_id)

        try:
            name = network.contract_call(
                method_type="read",
                contract_type="erc721main",
                address=contract_address,
                function_name="name",
                input_params=(),
                input_type=(),
                output_types=("string",),
            )
        except (ContractLogicError, ValueError):
            name = f"Untitled Collection {contract_address}"

        try:
            symbol = network.contract_call(
                method_type="read",
                contract_type="erc721main",
                address=contract_address,
                function_name="symbol",
                input_params=(),
                input_type=(),
                output_types=("string",),
            )
        except (ContractLogicError, ValueError):
            symbol = None

        return name, symbol
