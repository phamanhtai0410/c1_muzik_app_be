from django.db import transaction

from scanners.base import HandlerABC
from src.accounts.models import AdvUser
from src.activity.models import TokenHistory
from src.games.import_limits import increment_import_requests
from src.store.models import Collection, Ownership, Status, Token, TransactionTracker


class HandlerTransferBurn(HandlerABC):
    TYPE = "transfer"

    @transaction.atomic
    def save_event(self, event_data):
        data = self.scanner.parse_data_transfer(event_data)
        # check if already processed or is mint
        network_tx = self.network.web3.eth.get_transaction(data.tx_hash)
        if (
            network_tx.get("to")
            and network_tx["to"].lower() == self.network.exchange_address.lower()
        ):
            self.logger.debug(
                f"New buy event in TransferHandler, ignoring: {data.tx_hash}"
            )
            return

        increment_import_requests(self.network)

        # get collection and token
        collection_address = self.contract.address
        collection = Collection.objects.filter(
            network=self.network,
            address__iexact=collection_address,
        ).first()
        if (
            TokenHistory.objects.filter(tx_hash=data.tx_hash).exists()
            and not collection.is_imported
        ):
            self.logger.debug(f"History with tx hash {data.tx_hash} exists")
            return
        if not collection:
            self.logger.warning(
                f"Collection not found. Network: {self.network}, address: {collection_address}"
            )
            return
        if (
            TokenHistory.objects.filter(tx_hash=data.tx_hash).exists()
            and not collection.is_imported
        ):
            self.logger.debug(f"History with tx hash {data.tx_hash} exists")
            return
        token_id = data.token_id
        token = self.get_buyable_token(
            token_id=token_id,
            collection=collection,
        )
        if token is None and not collection.is_imported:
            self.logger.warning("Token not found")
            return

        # define if it is mint, transfer or burn and process if necessary
        if (
            data.old_owner == self.scanner.EMPTY_ADDRESS.lower()
            and collection.is_imported
        ):
            if TokenHistory.objects.filter(
                tx_hash=data.tx_hash, token__internal_id=data.token_id
            ).exists():
                self.logger.warning("already imported")
                return
            self.logger.debug(f"New mint (imported) event: {data}")
            new_owner = self.get_owner(data.new_owner)
            self.imported_mint_event(
                token_id=data.token_id,
                tx_hash=data.tx_hash,
                amount=data.amount,
                owner=new_owner,
                collection=collection,
            )
        elif data.old_owner == self.scanner.EMPTY_ADDRESS.lower():
            self.logger.debug(
                f"New mint event in TransferHandler, ignoring: {data.tx_hash}"
            )
            return

        elif data.new_owner == self.scanner.EMPTY_ADDRESS.lower():
            self.logger.debug(f"New burn event: {data}")
            old_owner = self.get_owner(data.old_owner)
            self.burn_event(
                token=token,
                tx_hash=data.tx_hash,
                amount=data.amount,
                old_owner=old_owner,
            )
            self.ownership_quantity_update(
                token=token,
                old_owner=old_owner,
                new_owner=None,
                amount=data.amount,
            )
        else:
            self.logger.debug(f"New transfer event: {data}")
            new_owner = self.get_owner(data.new_owner)
            old_owner = self.get_owner(data.old_owner)

            self.transfer_event(
                token=token,
                tx_hash=data.tx_hash,
                token_id=token_id,
                new_owner=new_owner,
                old_owner=old_owner,
                amount=data.amount,
            )
            self.ownership_quantity_update(
                token=token,
                old_owner=old_owner,
                new_owner=new_owner,
                amount=data.amount,
            )

    def get_buyable_token(
        self,
        token_id: int,
        collection: Collection,
    ) -> Token:
        return Token.objects.filter(
            internal_id=token_id,
            collection=collection,
        ).first()

    def burn_event(
        self,
        token: Token,
        tx_hash: str,
        amount: int,
        old_owner: AdvUser,
    ) -> None:
        token.total_supply = max(int(token.total_supply) - int(amount), 0)
        if token.total_supply == 0:
            token.status = Status.BURNED
            token.bids.all().delete()
        token.save()
        TokenHistory.objects.get_or_create(
            token=token,
            tx_hash=tx_hash,
            method="Burn",
            new_owner=None,
            old_owner=old_owner,
            price=None,
            amount=amount,
        )
        TransactionTracker.objects.filter(tx_hash__iexact=tx_hash).delete()

    def transfer_event(
        self,
        token: Token,
        tx_hash: str,
        token_id: int,
        new_owner: AdvUser,
        old_owner: AdvUser,
        amount: int,
    ) -> None:
        TokenHistory.objects.get_or_create(
            token=token,
            tx_hash=tx_hash,
            method="Transfer",
            new_owner=new_owner,
            old_owner=old_owner,
            price=None,
            amount=amount,
        )
        TransactionTracker.objects.filter(tx_hash__iexact=tx_hash).delete()

    def ownership_quantity_update(
        self,
        token: Token,
        old_owner: AdvUser,
        new_owner: AdvUser,
        amount: int,
    ) -> None:
        if old_owner is not None:
            try:
                ownership = Ownership.objects.get(owner=old_owner, token=token)
            except Ownership.DoesNotExist:
                self.logger.warning(
                    f"Ownership is not found: owner {old_owner}, token {token}"
                )
                return
            ownership.quantity = max(int(ownership.quantity) - int(amount), 0)
            ownership.save()

        if new_owner is not None:
            ownership, created = Ownership.objects.get_or_create(
                owner=new_owner,
                token=token,
            )
            if created:
                ownership.quantity = amount
            else:
                ownership.quantity += amount
            ownership.save()
            if created:
                token.owners.add(new_owner)

    def imported_mint_event(
        self,
        token_id: int,
        tx_hash: str,
        amount: int,
        owner: AdvUser,
        collection: Collection,
    ) -> None:
        if TokenHistory.objects.filter(
            token__internal_id=token_id, method="Mint", token__collection=collection
        ).exists():
            self.logger.warning(f"already minted: {collection} #{token_id}")
            return
        token = Token.objects.create(
            collection=collection,
            internal_id=token_id,
            status=Status.IMPORTING,
            creator=owner,
            name=f"{collection.name}#{token_id}",
            total_supply=amount,
        )

        Ownership.objects.get_or_create(owner=owner, token=token, quantity=amount)

        TokenHistory.objects.get_or_create(
            token=token,
            tx_hash=tx_hash,
            method="Mint",
            amount=amount,
            old_owner=owner,
            new_owner=None,
            price=None,
        )

    def mark_synced(self) -> None:
        collection_address = self.contract.address
        collection = Collection.objects.filter(
            network=self.network,
            address__iexact=collection_address,
            status=Status.IMPORTING,
        ).first()
        if not collection:
            self.logger.warning(
                f"Collection not found. Network: {self.network}, address: {collection_address}"
            )
            return
        collection.status = Status.COMMITTED
        collection.save(
            update_fields=[
                "status",
            ]
        )
