from scanners.data_structures import DeployData


class DeployMixin:
    def get_events_deploy(self, last_checked_block, last_network_block):
        event = {
            "ERC721": self.network.get_erc721fabric_contract().events.NewInstance,
            "ERC1155": self.network.get_erc1155fabric_contract().events.NewInstance,
        }[self.contract_type]
        return event.createFilter(
            fromBlock=last_checked_block,
            toBlock=last_network_block,
        ).get_all_entries()

    def parse_data_deploy(self, event) -> DeployData:
        return DeployData(
            collection_name=event["args"]["name"],
            address=self.network.wrap_in_checksum(event["args"]["instance"]),
            deploy_block=event["blockNumber"],
            tx_hash=event["transactionHash"].hex(),
        )
