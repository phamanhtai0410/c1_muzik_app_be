from scanners.data_structures import ApprovalData


class ApprovalMixin:
    def get_events_approval(self, last_checked_block, last_network_block):
        # signature is similar
        event = self.network.get_erc721main_contract(
            self.contract.address
        ).events.ApprovalForAll
        return event.createFilter(
            fromBlock=last_checked_block,
            toBlock=last_network_block,
        ).get_all_entries()

    def parse_data_approval(self, event) -> ApprovalData:
        account = event["args"].get("owner").lower()
        operator = event["args"].get("operator").lower()
        is_approved = event["args"].get("approved")
        return ApprovalData(
            account=account,
            operator=operator,
            is_approved=is_approved,
        )
