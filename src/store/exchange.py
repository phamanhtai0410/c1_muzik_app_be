import logging
from typing import TYPE_CHECKING, List, Optional, Tuple

from django.apps import apps
from django.db.models import Sum

from src.accounts.models import AdvUser
from src.consts import (
    COLLECTION_CREATION_GAS_LIMIT,
    TOKEN_BUY_GAS_LIMIT,
    TOKEN_MINT_GAS_LIMIT,
    TOKEN_TRANSFER_GAS_LIMIT,
)
from src.settings import config
from src.utilities import RedisClient, sign_message

if TYPE_CHECKING:
    from src.store.models import Bid


class TokenExchange:
    """Class for interacting with contract"""

    def __init__(self, token):
        self.token = token

    def get_price(self, seller: "AdvUser") -> int:
        """
        Return price or minimal_bid with decimals.
        """
        ownership = self.token.ownerships.get(
            owner=seller,
            selling=True,
        )
        max_bid = self.token.get_highest_bid()
        bid_price = None
        if max_bid:
            bid_price = int(max_bid.amount * max_bid.currency.get_decimals)
        return ownership.price_with_decimals or bid_price

    def create_tx_tracker(
        self, seller: "AdvUser", amount: int, auction: bool = False
    ) -> None:
        track_amount = amount or 1
        tracker_model = apps.get_model("store", "TransactionTracker")

        ownership = self.token.ownerships.filter(owner=seller).first()

        tracker_model.objects.create(
            token=self.token, ownership=ownership, amount=track_amount, auction=auction
        )

        tracker_amount = tracker_model.objects.filter(ownership=ownership).aggregate(
            total_amount=Sum("amount")
        )["total_amount"]

        if ownership.selling_quantity <= int(tracker_amount):
            ownership.selling = False
            ownership.save()

    def sign_buy_message(
        self,
        order_id: int,
        from_to: list,
        instances: list,
        id_and_amount: list,
        token_receivers: list,
        all_amounts: list,
    ) -> str:
        types_list = [
            "uint256",
            "uint256",
            "address[2]",
            "address[2]",
            "uint256[2]",
            "address[]",
            "uint256[]",
            "uint256",
        ]
        values_list = [
            self.token.collection.network.chain_id,
            order_id,
            from_to,
            instances,
            id_and_amount,
            token_receivers,
            all_amounts,
            self.token.collection.network.deadline_timestamp,
        ]
        return sign_message(types_list, values_list)

    def buy(
        self,
        amount: int,
        buyer: "AdvUser",
        seller: "AdvUser",
        auction: bool = False,
    ) -> str:
        """
        :param int amount: count of purchased tokens (0 - for 721)
        :param AdvUser buyer: token buyer
        :param AdvUser seller: token seller
        :param bool auction: if true - send transaction from seller
        :return: initial tx
        """

        price = self.get_price(seller)  # get price with decimals

        self.create_tx_tracker(seller, amount, auction=auction)

        redis = RedisClient()
        order_id = redis.connection.incr("buy_order_id")

        # get adresses ethereum style
        seller_address = self.token.collection.network.wrap_in_checksum(seller.username)
        buyer_address = self.token.collection.network.wrap_in_checksum(buyer.username)

        # set checksum addresses from user - to user
        from_to = [
            self.token.collection.network.wrap_in_checksum(seller_address),
            self.token.collection.network.wrap_in_checksum(buyer_address),
        ]
        ownership = self.token.ownerships.filter(owner=seller).first()
        instances = [
            self.token.collection.network.wrap_in_checksum(
                self.token.collection.address
            ),
            self.token.collection.network.wrap_in_checksum(ownership.currency.address),
        ]
        id_and_amount = [int(self.token.internal_id), amount]

        gross_price_with_amount = price
        if not self.token.is_single:
            gross_price_with_amount = price * amount
        tx_value = 0
        # set value if native coin
        if ownership.currency.address.lower() == self.token.native_address:
            tx_value = gross_price_with_amount
        # get fee list and calculate amounts to all users
        token_receivers = [
            self.token.collection.network.wrap_in_checksum(
                self.token.collection.creator.username
            ),
            self.token.collection.network.wrap_in_checksum(
                self.token.collection.network.platform_fee_address
            ),
        ]
        royalty = int(
            gross_price_with_amount * self.token.collection.creator_royalty / 100
        )
        plaform_fee = int(
            gross_price_with_amount
            * self.token.collection.network.platform_fee_percentage
            / 100
        )
        net_price = int(gross_price_with_amount - royalty - plaform_fee)
        all_amounts = [net_price, royalty, plaform_fee]

        signature = self.sign_buy_message(
            order_id, from_to, instances, id_and_amount, token_receivers, all_amounts
        )
        # set input types and params for transaction
        if self.token.collection.network.network_type == "tron":
            input_types = ...
        else:
            input_types = (
                "uint256",
                "address[2]",
                "address[2]",
                "uint256[2]",
                "address[]",
                "uint256[]",
                "uint256",
                "bytes",
            )

        input_params = (
            order_id,
            from_to,
            instances,
            id_and_amount,
            token_receivers,
            all_amounts,
            self.token.collection.network.deadline_timestamp,
            signature,
        )

        nonce_username = buyer_address
        if auction:
            nonce_username = seller_address

        return self.token.collection.network.contract_call(
            method_type="write",
            contract_type="exchange",
            gas_limit=TOKEN_BUY_GAS_LIMIT,
            nonce_username=nonce_username,
            function_name="trade",
            input_params=input_params,
            input_type=input_types,
            tx_value=tx_value,
        )

    def get_valid_bid(self) -> Optional["Bid"]:
        """
        Return valid bid for token.
        If token hasn't bids (or valid bids) return None.
        """
        bids = self.token.bids.all().order_by("-amount")
        for bid in bids:
            check_valid = self.token.validator.check_validate_bid(
                user=bid.user, amount=bid.amount
            )
            if check_valid.errors is None:
                return bid
            bid.delete()
            continue

    @classmethod
    def end_auction_send(cls, tokens: list) -> Tuple[str, List[dict]]:
        network = tokens[0].collection.network
        from_to_addresses = []
        instances = []
        id_and_amounts = []
        token_receivers = []
        all_amounts = []
        history_data = []

        tracker_model = apps.get_model("store", "TransactionTracker")

        for token in tokens:
            ownership = token.ownerships.first()
            owner = token.ownerships.first().owner
            bid = cls(token).get_valid_bid()
            if not bid:
                ownership.selling = False
                ownership._end_auction = None
                ownership._start_auction = None
                ownership.selling_quantity = 0
                ownership.minimal_bid = None
                ownership.save(
                    update_fields=[
                        "selling",
                        "_end_auction",
                        "selling_quantity",
                        "_start_auction",
                        "minimal_bid",
                    ]
                )
                ownership.refresh_from_db()

                continue
            logging.info(f"End auction for {token} with bid {bid}")
            from_to_addresses.append(
                (
                    network.wrap_in_checksum(owner.username),
                    network.wrap_in_checksum(bid.user.username),
                )
            )
            instances.append(
                (
                    network.wrap_in_checksum(token.collection.address),
                    network.wrap_in_checksum(bid.currency.address),
                )
            )
            id_and_amounts.append(
                (
                    int(token.internal_id),
                    0,  # only 721 tokens
                )
            )
            gross_price = int(bid.amount * bid.currency.get_decimals)
            token_receivers.append(
                [
                    network.wrap_in_checksum(token.collection.creator.username),
                    network.wrap_in_checksum(network.platform_fee_address),
                ]
            )
            royalty = int(gross_price * token.collection.creator_royalty / 100)
            plaform_fee = int(
                gross_price * token.collection.network.platform_fee_percentage / 100
            )
            net_price = gross_price - royalty - plaform_fee
            all_amounts.append([net_price, royalty, plaform_fee])
            history_data.append(
                {
                    "old_owner": owner,
                    "new_owner": bid.user,
                    "id": token.id,
                    "amount": bid.amount,
                }
            )
            # create tx tracker instance

            tracker_model.objects.create(token=token, bid=bid, auction=True)
            ownership.selling = False
            ownership._end_auction = None
            ownership._start_auction = None
            ownership.currency = None
            ownership.minimal_bid = None
            ownership.save(
                update_fields=[
                    "selling",
                    "_end_auction",
                    "_start_auction",
                    "currency",
                    "minimal_bid",
                ]
            )
        if not from_to_addresses:
            return None, []
        tx_hash = network.contract_call(
            method_type="write",
            contract_type="exchange",
            gas_limit=int(TOKEN_BUY_GAS_LIMIT) * len(tokens),
            nonce_username=config.SIGNER_ADDRESS,
            function_name="forceTradeBatch",
            input_params=(
                tuple(from_to_addresses),
                tuple(instances),
                tuple(id_and_amounts),
                tuple(token_receivers),
                tuple(all_amounts),
            ),
            input_type=[
                "address[2][]",
                "address[2][]",
                "uint256[2][]",
                "address[][]",
                "uint256[][]",
            ],
            send=True,
        )

        logging.info(f"Auction for tokens {tokens} ended. Tx hash: {tx_hash}")
        return tx_hash, history_data

    def mint(
        self,
        ipfs,
        collection,
        total_supply,
        user,
    ):
        mint_id = self.token.mint_id
        collection_address = collection.network.wrap_in_checksum(collection.address)
        type_list = ["uint256", "uint256", "address", "address", "string", "uint256"]
        sign_msg = [
            collection.network.chain_id,
            mint_id,
            collection.network.wrap_in_checksum(user.username),
            collection_address,
            ipfs,
            collection.network.deadline_timestamp,
        ]
        # add amount for 1155 tokens
        if not collection.is_single:
            type_list.insert(4, "uint256")
            sign_msg.insert(4, total_supply)

        signature = sign_message(type_list, sign_msg)
        tx_msg = [mint_id, ipfs, collection.network.deadline_timestamp, signature]
        if not collection.is_single:
            tx_msg.insert(1, int(total_supply))
        return collection.create_token(
            collection.network.wrap_in_checksum(user.username), tx_msg
        )

    def transfer(self, old_owner, new_owner, amount=None):
        if self.token.is_single:
            return self.token.collection.network.contract_call(
                method_type="write",
                contract_type="erc721main",
                address=self.token.collection.address,
                gas_limit=TOKEN_TRANSFER_GAS_LIMIT,
                nonce_username=old_owner.username,
                tx_value=None,
                function_name="transferFrom",
                input_params=(
                    self.token.collection.network.wrap_in_checksum(old_owner.username),
                    self.token.collection.network.wrap_in_checksum(new_owner),
                    int(self.token.internal_id),
                ),
                input_type=("string", "string", "uint256"),
                is1155=False,
            )
        return self.token.collection.network.contract_call(
            method_type="write",
            contract_type="erc1155main",
            address=self.token.collection.address,
            gas_limit=TOKEN_TRANSFER_GAS_LIMIT,
            nonce_username=old_owner.username,
            tx_value=None,
            function_name="safeTransferFrom",
            input_params=(
                self.token.collection.network.wrap_in_checksum(old_owner.username),
                self.token.collection.network.wrap_in_checksum(new_owner),
                int(self.token.internal_id),
                int(amount),
                "0x00",
            ),
            input_type=("string", "string", "uint256", "uint256", "string"),
            is1155=True,
        )

    def burn(self, user=None, amount=None):
        if self.token.is_single:
            return self.token.collection.network.contract_call(
                method_type="write",
                contract_type="erc721main",
                address=self.token.collection.address,
                gas_limit=TOKEN_MINT_GAS_LIMIT,
                nonce_username=user.username,
                tx_value=None,
                function_name="burn",
                input_params=(self.token.internal_id,),
                input_type=("uint256",),
                is1155=False,
            )

        return self.token.collection.network.contract_call(
            method_type="write",
            contract_type="erc1155main",
            address=self.token.collection.address,
            gas_limit=TOKEN_MINT_GAS_LIMIT,
            nonce_username=user.username,
            tx_value=None,
            function_name="burn",
            input_params=(
                self.token.collection.network.wrap_in_checksum(user.username),
                int(self.token.internal_id),
                int(amount),
            ),
            input_type=("string", "uint256", "uint256"),
            is1155=True,
        )


class CollectionExchange:
    """Class for interacting with contract"""

    def __init__(self, collection):
        self.collection = collection

    @classmethod
    def create_contract(cls, name, symbol, standard, owner, network):
        redis = RedisClient()
        order_id = redis.connection.incr("deploy_order_id")
        field_name = (
            "fabric721_address" if standard == "ERC721" else "fabric1155_address"
        )
        sign_types = [
            "uint256",
            "uint256",
            "address",
            "address",
            "string",
            "string",
            "uint256",
        ]
        message = [
            network.chain_id,
            order_id,
            network.wrap_in_checksum(owner.username),
            network.wrap_in_checksum(getattr(network, field_name)),
            name,
            symbol,
            network.deadline_timestamp,
        ]
        signature = sign_message(
            sign_types,
            message,
        )
        tx_types = ["uint256", "string", "string", "uint256", "bytes"]
        tx_data = [order_id, name, symbol, network.deadline_timestamp, signature]

        if standard == "ERC721":
            return network.contract_call(
                method_type="write",
                contract_type="erc721fabric",
                gas_limit=COLLECTION_CREATION_GAS_LIMIT,
                nonce_username=owner.username,
                tx_value=None,
                function_name="deployERC721Instance",
                input_params=tx_data,
                input_type=tx_types,
                send=False,
            )

        return network.contract_call(
            method_type="write",
            contract_type="erc1155fabric",
            gas_limit=COLLECTION_CREATION_GAS_LIMIT,
            nonce_username=owner.username,
            tx_value=None,
            function_name="deployERC1155Instance",
            input_params=tx_data,
            send=False,
            input_type=tx_types,
        )
