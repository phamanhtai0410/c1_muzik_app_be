import logging
import threading

from scanners.utils import get_scanner, never_fall
from src.games.import_limits import (
    get_import_requests_exceeded,
    increment_import_requests,
)
from src.networks.models import Network


class ScannerAbsolute(threading.Thread):
    """
    ScannerAbsolute launches a scanner of the appropriate type
    depending on the network and calls the resulting handler.
    """

    def __init__(
        self,
        network: Network,
        handler: object,
        contract_type: str = None,
        contract: object = None,
        synced: bool = None,
    ) -> None:
        super().__init__()
        self.network = network
        self.contract_type = contract_type  # ERC721/ ERC1155
        self.contract = contract
        self.scanner = get_scanner(
            self.network, self.contract_type, self.contract, synced=synced
        )
        self.handler = handler(
            self.network, self.scanner, self.contract, standard=self.contract_type
        )
        self.block_range = 5000

    def run(self):
        self.start_polling()

    @property
    def block_name(self) -> str:
        name = f"{self.handler.TYPE}_{self.network.name}"
        if self.contract:
            contract = (
                self.contract if type(self.contract) == str else self.contract.address
            )
            name += f"_{contract}"
        name += f"_{self.contract_type}" if self.contract_type else ""
        return name

    @never_fall
    def start_polling(self) -> None:
        while True:
            if self.scanner.synced is False and get_import_requests_exceeded(
                self.network
            ):
                self.scanner.sleep()
                continue

            last_checked_block = self.scanner.get_last_block(self.block_name)
            last_network_block = self.scanner.get_last_cached_block()

            if not last_checked_block or not last_network_block:
                self.scanner.sleep()
                continue

            last_network_block -= 5

            if last_network_block - last_checked_block < 5:
                self.scanner.try_change_synced_status()
                self.scanner.sleep()
                continue
            # filter cannot support more than 5000 blocks at one query
            if last_network_block - last_checked_block > self.block_range:
                last_network_block = last_checked_block + self.block_range - 1

            try:
                event_list = getattr(self.scanner, f"get_events_{self.handler.TYPE}")(
                    last_checked_block,
                    last_network_block,
                )
            except ValueError as e:
                logging.error(f"Exception: {repr(e)}")
                args = e.args
                if (
                    args
                    and args[0]
                    and isinstance(args[0], dict)
                    and args[0].get("code") == -32005
                ):
                    self.block_range = int(self.block_range / 2)
                    print(f"reduced to {self.block_range}")
                continue
            self.block_range = 5000

            if event_list:
                list(map(self.handler.save_event, event_list))

            if not self.scanner.synced:
                increment_import_requests(self.network)

            if self.scanner.synced_status_changed:
                self.handler.mark_synced()
                self.scanner.synced_status_changed = False

            self.scanner.save_last_block(self.block_name, last_network_block)
            self.scanner.sleep(self.handler.TIMEOUT)
