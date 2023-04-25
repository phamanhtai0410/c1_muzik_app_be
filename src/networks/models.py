from datetime import timedelta
from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone
from web3 import Web3

from contracts import (
    ERC721_FABRIC,
    ERC721_MAIN,
    ERC1155_FABRIC,
    ERC1155_MAIN,
    EXCHANGE,
    PROMOTION,
    WETH_ABI,
)
from src.settings import config
from src.utilities import get_media_from_ipfs

if TYPE_CHECKING:
    from web3.contract import Contract
    from web3.types import ABI


class Types(models.TextChoices):
    ethereum = "ethereum"


class Address:
    def __init__(self, address):
        self.address = address


class Network(models.Model):
    """
    Represent different networks as different blockchains,
    in witch we have our contracts.
    """

    icon = models.CharField(max_length=200, blank=True, null=True, default=None)
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=10, null=True, blank=True, default=None)
    needs_middleware = models.BooleanField(default=False)
    chain_id = models.PositiveIntegerField()
    native_symbol = models.CharField(max_length=10, blank=True, null=True, default=None)
    exchange_address = models.CharField(max_length=128)
    minimal_balance = models.FloatField(default=1)
    fabric721_address = models.CharField(max_length=128)
    fabric1155_address = models.CharField(max_length=128)
    promotion_address = models.CharField(max_length=128)
    platform_fee_address = models.CharField(max_length=128)
    platform_fee_percentage = models.DecimalField(max_digits=4, decimal_places=2)
    network_type = models.CharField(
        max_length=20,
        choices=Types.choices,
        default=Types.ethereum,
    )
    deadline = models.DurationField(default=timedelta())
    native_address = models.CharField(
        max_length=128, default="0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
    )
    moralis_slug = models.CharField(max_length=20, default="goerli")
    api_domain = models.CharField(max_length=100, default="api-goerli.etherscan.io")
    api_key = models.CharField(max_length=200)
    auction_timeout = models.DurationField(default=timedelta())
    daily_import_requests = models.IntegerField(null=True, default=None)

    def __str__(self):
        return self.name

    @property
    def ipfs_icon(self):
        if self.icon:
            return get_media_from_ipfs(self.icon)

    @property
    def web3(self):
        return Web3(
            Web3.HTTPProvider(self.providers.all().values_list("endpoint", flat=True))
        )

    @property
    def deadline_timestamp(self) -> int:
        deadline = timezone.now() + self.deadline
        return int(deadline.timestamp())

    def _get_contract_by_abi(self, abi: "ABI", address: str = None) -> "Contract":
        if address:
            address = self.wrap_in_checksum(address)
        contract = self.web3.eth.contract(address=address, abi=abi)
        return contract

    def get_erc721fabric_contract(self) -> "Contract":
        return self._get_contract_by_abi(ERC721_FABRIC, self.fabric721_address)

    def get_erc1155fabric_contract(self) -> "Contract":
        return self._get_contract_by_abi(ERC1155_FABRIC, self.fabric1155_address)

    def get_exchange_contract(self) -> "Contract":
        return self._get_contract_by_abi(EXCHANGE, self.exchange_address)

    def get_erc721main_contract(self, address: str = None) -> "Contract":
        if self.network_type == Types.ethereum:
            return self._get_contract_by_abi(ERC721_MAIN, address)
        return Address(address)

    def get_erc1155main_contract(self, address: str = None) -> "Contract":
        if self.network_type == Types.ethereum:
            return self._get_contract_by_abi(ERC1155_MAIN, address)
        return Address(address)

    def get_token_contract(self, address: str = None) -> "Contract":
        if self.network_type == Types.ethereum:
            return self._get_contract_by_abi(WETH_ABI, address)
        return Address(address)

    def get_promotion_contract(self) -> "Contract":
        return self._get_contract_by_abi(PROMOTION, self.promotion_address)

    def get_signer_balance(self):
        return self.web3.eth.get_balance(config.SIGNER_ADDRESS)

    def get_last_block(self) -> int:
        return self.web3.eth.block_number

    def wrap_in_checksum(self, address: str) -> str:
        """Wrap address to checksum for EVM"""
        if self.network_type == Types.ethereum:
            return self.web3.toChecksumAddress(address)
        return address

    def contract_call(self, method_type: str, **kwargs):
        """
        redirects to ethereum/tron/whatever_functional_we_will_add_later read/write method
        kwargs example for ethereum read method:
        {
        address: str, #address of contract if necessary
        contract_type: str, #contract type for calling web3 instance via get_{contract_type}_method()
        function_name: str, #function name for function selector
        input_types: tuple, #tuple of function param types (i.e. ('address', 'uint256')) for stupid tron
        input_params: tuple, #tuple of function param values
        output_types: tuple, #tuple of output param types if necessary (for stupid tron)
        }
        """
        return getattr(self, f"execute_{self.network_type}_{method_type}_method")(
            **kwargs
        )

    def execute_ethereum_read_method(self, **kwargs):
        contract_type = kwargs.get("contract_type")
        address = kwargs.get("address")
        function_name = kwargs.get("function_name")
        input_params = kwargs.get("input_params")
        if address:
            contract = getattr(self, f"get_{contract_type}_contract")(address)
        else:
            contract = getattr(self, f"get_{contract_type}_contract")()
        # to not send None into function args
        if input_params:
            return getattr(contract.functions, function_name)(*input_params).call()
        return getattr(contract.functions, function_name)().call()

    def execute_ethereum_write_method(self, **kwargs):
        contract_type = kwargs.get("contract_type")
        address = kwargs.get("address")
        send = kwargs.get("send", False)
        if address:
            contract = getattr(self, f"get_{contract_type}_contract")(address)
        else:
            contract = getattr(self, f"get_{contract_type}_contract")()

        gas_limit = kwargs.get("gas_limit")
        nonce_username = kwargs.get("nonce_username")
        if send:
            nonce_username = config.SIGNER_ADDRESS
        tx_value = kwargs.get("tx_value")
        assert gas_limit is not None
        assert nonce_username is not None

        tx_params = {
            "chainId": self.web3.eth.chainId,
            "gas": gas_limit,
            "nonce": self.web3.eth.getTransactionCount(
                self.wrap_in_checksum(nonce_username), "pending"
            ),
            "gasPrice": self.web3.eth.gasPrice,
        }
        if tx_value is not None:
            tx_params["value"] = tx_value

        function_name = kwargs.get("function_name")
        input_params = kwargs.get("input_params")
        # to not send None into function args
        if input_params:
            initial_tx = getattr(contract.functions, function_name)(
                *input_params
            ).buildTransaction(tx_params)
        else:
            initial_tx = getattr(contract.functions, function_name)().buildTransaction(
                tx_params
            )
        if send:
            signed_tx = self.web3.eth.account.sign_transaction(
                initial_tx, config.PRIV_KEY
            )
            tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)
            return tx_hash.hex()
        # pop gas from tx if not autosending so frontend can get it from metamask
        initial_tx.pop("gas")
        initial_tx.pop("gasPrice")
        initial_tx["value"] = str(initial_tx["value"])
        return initial_tx


class Provider(models.Model):
    endpoint = models.CharField(max_length=256)
    network = models.ForeignKey(
        Network,
        on_delete=models.CASCADE,
        related_name="providers",
    )

    def __str__(self):
        return self.endpoint
