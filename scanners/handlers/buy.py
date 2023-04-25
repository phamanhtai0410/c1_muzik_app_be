from decimal import Decimal

from django.db import transaction

from scanners.base import HandlerABC
from src.activity.models import TokenHistory
from src.rates.models import UsdRate
from src.store.models import Bid, Ownership, Token, TransactionTracker


class HandlerBuy(HandlerABC):
    TYPE = "buy"

    @transaction.atomic
    def save_event(self, event_data):
        data = self.scanner.parse_data_buy(event_data)
        self.logger.debug(f"New event: {data}")

        # check if already processed
        if TokenHistory.objects.filter(tx_hash=data.tx_hash).exists():
            self.logger.debug(f"History with tx hash {data.tx_hash} exists")
            return

        # 721 contract thinks amount is always zero
        if data.amount == 0:
            data.amount = 1
        token = Token.objects.committed().filter(
            collection__address__iexact=data.collection_address,
            internal_id=data.token_id,
        ).first()
        if not token:
            self.logger.warning(f"token with internal_id {data.token_id} and collection address {data.collection_address} not found, skipping")
            return
        auction = self.get_auction(token)
        self.buy_token(token, data)
        self.refresh_token_history(token, data, auction)

    def buy_token(self, token: Token, data):
        new_owner = self.get_owner(data.buyer)
        old_owner = self.get_owner(data.seller)

        # update new owner data
        owner = Ownership.objects.filter(
            owner=new_owner,
            token=token,
        ).first()
        if owner:
            owner.quantity = owner.quantity + data.amount
            owner.save()
        else:
            Ownership.objects.create(
                owner=new_owner,
                token=token,
                quantity=data.amount,
            )

        # update old_owner data
        try:
            owner = Ownership.objects.get(owner=old_owner, token=token)
        except Ownership.DoesNotExist:
            self.logger.warning(f"Ownership not found owner {old_owner}, token {token}")
            return
        owner.quantity = max(int(owner.quantity) - int(data.amount), 0)
        owner.selling_quantity = max(int(owner.selling_quantity) - int(data.amount), 0)
        owner.save()

        # delete bids and tracker
        bet = Bid.objects.filter(token=token).order_by("-amount")
        sell_amount = data.amount
        if bet.exists():
            if sell_amount == bet.first().quantity:
                bet.delete()
            else:
                bet = bet.first()
                bet.quantity -= sell_amount
                bet.save()
        TransactionTracker.objects.filter(tx_hash__iexact=data.tx_hash).delete()

    def refresh_token_history(self, token, data, auction=False) -> TokenHistory:
        new_owner = self.get_owner(data.buyer)
        old_owner = self.get_owner(data.seller)

        currency = UsdRate.objects.filter(
            network=token.collection.network,
            address__iexact=data.currency_address,
        ).first()

        decimals = currency.get_decimals
        price = Decimal(Decimal(data.price) / Decimal(decimals))

        token_history_method = "AuctionWin" if auction else "Buy"
        token_history, _ = TokenHistory.objects.get_or_create(
            tx_hash=data.tx_hash,
            defaults={
                "method": token_history_method,
                "amount": data.amount,
                "price": price,
                "token": token,
                "new_owner": new_owner,
                "old_owner": old_owner,
                "currency": currency,
            },
        )
        return token_history

    def get_auction(self, token) -> bool:
        return TransactionTracker.objects.filter(token=token, auction=True).exists()
