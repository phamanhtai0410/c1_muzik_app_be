import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

from src.accounts.models import AdvUser
from src.settings import config
from src.store.models import Collection
from src.utilities import RedisClient

_log_format = (
    "%(asctime)s - [%(levelname)s] - %(filename)s (line %(lineno)d) - %(message)s"
)

_datetime_format = "%d.%m.%Y %H:%M:%S"

loggers = {}


class HandlerABC(ABC):
    TIMEOUT = None

    def __init__(self, network, scanner, contract=None, standard=None) -> None:
        self.network = network
        self.scanner = scanner
        self.contract = contract
        self.standard = standard

        logger_name = f"scanner_{self.TYPE}_{self.network}"

        # This is necessary so that records are not duplicated.
        if not loggers.get(logger_name):
            loggers[logger_name] = self.get_logger(logger_name)
        self.logger = loggers.get(logger_name)

    def get_owner(self, owner_address: str) -> Optional[AdvUser]:
        try:
            user = AdvUser.objects.get(username__iexact=owner_address)
        except AdvUser.DoesNotExist:
            user = AdvUser.objects.create(username=owner_address.lower())
        return user

    def get_file_handler(self, name):
        file_handler = logging.FileHandler(f"logs/{name}.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(_log_format, datefmt=_datetime_format)
        )
        return file_handler

    def get_stream_handler(self):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(
            logging.Formatter(_log_format, datefmt=_datetime_format)
        )
        return stream_handler

    def get_logger(self, name):
        logger = logging.getLogger(name)
        logging.getLogger("urllib3").setLevel(logging.ERROR)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(self.get_file_handler(name))
        logger.addHandler(self.get_stream_handler())
        return logger

    def mark_synced(self) -> None:
        # needed only for specific handlers, such as MintTransferBurn
        pass

    @abstractmethod
    def save_event(self) -> None:
        ...


class ScannerABC(ABC):
    def __init__(self, network, contract_type=None, contract=None, synced=None):
        self.network = network
        self.contract_type = contract_type
        self.contract = contract
        self.synced = synced
        self.synced_status_changed = False

    def sleep(self, custom_timeout=None) -> None:
        time.sleep(custom_timeout or config.SCANNER_SLEEP)

    def save_last_block(self, name, block) -> None:
        redis_ = RedisClient()
        redis_.connection.set(name, int(block) + 1)

    def get_last_block(self, name) -> int:
        redis_ = RedisClient()
        last_block_number = redis_.connection.get(name)
        if not last_block_number:
            # try to get deploy block for Collection
            if self.contract_type and self.contract:
                collection = Collection.objects.get(
                    address__iexact=self.contract.address, network=self.network
                )
                if collection:
                    if collection.deploy_block:
                        deploy_block = collection.deploy_block - 1
                    else:
                        deploy_block = None
                    last_block_number = deploy_block or self.get_last_network_block()
            else:
                last_block_number = self.get_last_network_block()
            if not last_block_number:
                return None
            self.save_last_block(name, last_block_number)
        return int(last_block_number)

    def get_last_cached_block(self) -> int:
        redis_ = RedisClient()
        last_block_number = redis_.connection.get(self.network.name)
        if not last_block_number:
            last_block_number = int(self.get_last_network_block())
            redis_.connection.set(self.network.name, last_block_number, ex=10)
        return int(last_block_number)

    def try_change_synced_status(self):
        if self.synced is False:
            self.synced = True
            self.synced_status_changed = True

    def get_last_network_block(self) -> int:
        return self.network.get_last_block()
