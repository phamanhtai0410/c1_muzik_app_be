from scanners.data_structures import BuyData


class BuyMixin:
    def get_events_buy(self, last_checked_block, last_network_block):
        return (
            self.network.get_exchange_contract()
            .events.Trade.createFilter(
                fromBlock=last_checked_block,
                toBlock=last_network_block,
            )
            .get_all_entries()
        )

    def parse_data_buy(self, event) -> BuyData:
        return BuyData(
            buyer=event["args"]["fromTo"][1].lower(),
            seller=event["args"]["fromTo"][0].lower(),
            collection_address=event["args"]["nftAndToken"][0].lower(),
            currency_address=event["args"]["nftAndToken"][1].lower(),
            price=sum(event["args"]["allAmounts"]),
            amount=event["args"]["idAndAmount"][1],
            tx_hash=event["transactionHash"].hex(),
            token_id=event["args"]["idAndAmount"][0],
        )
