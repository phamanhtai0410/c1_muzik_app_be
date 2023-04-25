from django.db import transaction

from scanners.base import HandlerABC
from src.activity.models import TokenHistory
from src.store.models import Collection, Status


class HandlerMint(HandlerABC):
    TYPE = "mint"

    @transaction.atomic
    def save_event(self, event_data):
        data = self.scanner.parse_data_mint(event_data)
        self.logger.debug(f"New event: {data}")

        # find collection and token
        collection_address = self.contract.address
        collection = Collection.objects.filter(
            standard=self.standard, address=collection_address
        ).first()
        if not collection:
            self.logger.warning(
                f"Collection not found. Network: {self.network}, address: {collection_address}"
            )
            return
        if collection.is_imported:
            self.logger.warning(
                f"Collection have is_imported flag. Skipping (Network: {self.network}, address: {collection_address}"
            )
            return
        token = collection.tokens.filter(mint_id=data.mint_id).first()
        if not token:
            self.logger.warning(
                f"Token not found. collection address {collection.address}, mint_id {data.mint_id}"
            )
            return

        # update token data and create mint history
        token.status = Status.COMMITTED
        token.internal_id = data.internal_id
        token.save()
        owner = self.get_owner(data.owner)
        TokenHistory.objects.get_or_create(
            token=token,
            tx_hash=data.tx_hash,
            method="Mint",
            amount=token.total_supply,
            new_owner=None,
            old_owner=owner,
            price=None,
        )

        # create listing history if token set on sale
        ownership = token.ownerships.first()
        price = ownership.price_or_minimal_bid
        currency = ownership.currency
        if ownership.selling and price:
            TokenHistory.objects.create(
                token=token,
                old_owner=token.creator,
                new_owner=None,
                method="Listing",
                tx_hash=data.tx_hash,
                amount=token.total_supply,
                price=price,
                currency=currency,
            )
