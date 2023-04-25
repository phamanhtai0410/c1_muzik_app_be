from scanners.data_structures import MintData


class MintMixin:
    def get_events_mint(self, last_checked_block, last_network_block):
        event = {
            "ERC721": self.network.get_erc721main_contract(
                self.contract.address
            ).events.Mint,
            "ERC1155": self.network.get_erc1155main_contract(
                self.contract.address
            ).events.Mint,
        }[self.contract_type]
        return event.createFilter(
            fromBlock=last_checked_block,
            toBlock=last_network_block,
        ).get_all_entries()

    def parse_data_mint(self, event) -> MintData:
        # 721 and 1155 contracts have different args of event and 721 returns id+1
        token_id = event["args"].get("tokenID")
        if token_id is None:
            token_id = event["args"]["totalSupply"]
        return MintData(
            internal_id=token_id,
            mint_id=event["args"]["mintID"],
            tx_hash=event["transactionHash"].hex(),
            amount=event["args"].get("amount", 1),
            owner=event["args"]["sender"],
        )
