from scanners.data_structures import TransferData


class TransferMixin:
    def get_events_transfer(self, last_checked_block, last_network_block):
        event = {
            "ERC721": self.network.get_erc721main_contract(
                self.contract.address
            ).events.Transfer,
            "ERC1155": self.network.get_erc1155main_contract(
                self.contract.address
            ).events.TransferSingle,
        }[self.contract_type]
        return event.createFilter(
            fromBlock=last_checked_block,
            toBlock=last_network_block,
        ).get_all_entries()

    def parse_data_transfer(self, event) -> TransferData:
        # 721 and 1155 contracts have different args of event
        token_id = event["args"].get("tokenId")
        if token_id is None:
            token_id = event["args"].get("id")
        amount = event["args"].get("value", 1)
        if int(amount) == 0:
            amount = 1
        return TransferData(
            token_id=token_id,
            new_owner=event["args"]["to"].lower(),
            old_owner=event["args"]["from"].lower(),
            tx_hash=event["transactionHash"].hex(),
            amount=amount,
        )
