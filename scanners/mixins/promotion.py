from scanners.data_structures import PromotionData


class PromotionMixin:
    def get_events_promotion(self, last_checked_block, last_network_block):
        event = self.network.get_promotion_contract().events.PromotionSuccess
        return event.createFilter(
            fromBlock=last_checked_block,
            toBlock=last_network_block,
        ).get_all_entries()

    def parse_data_promotion(self, event) -> "PromotionData":
        return PromotionData(
            package=event["args"].get("package"),
            collection_address=event["args"].get("promotionToken"),
            token_id=event["args"].get("promotionId"),
            buyer=event["args"].get("sender"),
            chain_id=event["args"]["promotionChainId"],
        )
