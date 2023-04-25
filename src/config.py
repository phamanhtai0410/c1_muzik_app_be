import os
from dataclasses import dataclass
from typing import List, Optional

import yaml
from marshmallow_dataclass import class_schema


@dataclass
class Network:
    name: str
    needs_middleware: bool
    native_symbol: str
    chain_id: int
    fabric721_address: str
    fabric1155_address: str
    exchange_address: str
    promotion_address: str
    platform_fee_address: str
    platform_fee_percentage: float
    network_type: str
    deadline: int


@dataclass
class Provider:
    endpoint: str
    network: str


@dataclass
class Email:
    role: str
    address: str
    password: Optional[str]
    smtp: Optional[str]
    port: Optional[int]
    use_tls: Optional[bool]


@dataclass
class Config:
    ALLOWED_HOSTS: list
    SECRET_KEY: str
    DEBUG: bool

    IPFS_CLIENT: str
    IPFS_DOMAIN: str
    IPFS_PORT: int
    SCANNER_SLEEP: int

    @dataclass
    class SortStatus:
        recent: str
        cheapest: str
        highest: str

    @dataclass
    class SearchType:
        items: str
        users: str
        collections: str

    @dataclass
    class UsdRate:
        coin_node: str
        symbol: str
        name: str
        image: str
        address: str
        decimal: int
        network: str

    @dataclass
    class Intervals:
        every: int
        period: str
        pk: int

    @dataclass
    class Crontabs:
        minute: int
        hour: int
        pk: int

    @dataclass
    class PeriodicTasks:
        name: str
        task: str
        interval: Optional[int]
        crontab: Optional[int]
        enabled: bool

    SORT_STATUSES: SortStatus

    SEARCH_TYPES: SearchType
    USER_URL_FIELD: str

    SIGNER_ADDRESS: str
    CAPTCHA_SECRET: Optional[str]
    CAPTCHA_URL: Optional[str]
    PRIV_KEY: str
    BOTS: dict

    DEFAULT_NETWORK: Optional[str]
    TX_TRACKER_TIMEOUT: int

    REDIS_EXPIRATION_TIME: int
    CLEAR_TOKEN_TAG_NEW_TIME: int

    API_URL: str
    MORALIS_API_KEY: str
    MORALIS_TRANSFER_URL: str
    ETHERSCAN_TX_URL: str

    RATES_CHECKER_TIMEOUT: int
    TRENDING_TRACKER_TIME: int
    NOTIFICATION_COUNT: int

    TITLE: str
    DESCRIPTION: str
    ITEMS_PER_PAGE: int

    NETWORKS: List[Network]
    PROVIDERS: List[Provider]
    USD_RATES: List[UsdRate]
    EMAILS: List[Email]
    MAX_ROYALTY_PERCENTAGE: float

    INTERVALS: List[Intervals]
    CRONTABS: List[Crontabs]
    PERIODIC_TASKS: List[PeriodicTasks]

    REDIS_HOST: str
    REDIS_PORT: int

    SENTRY_DSN: str
    PENDING_EXPIRATION_MINUTES: int
    INCLUDE_FOLLOWING_NOTIFICATIONS: Optional[bool]

    WS_TOKEN_AGE_SECONDS: Optional[int]


config_path = "/../config.yaml"
if os.getenv("IS_TEST", False):
    config_path = "/../config.example.yaml"


with open(os.path.dirname(__file__) + config_path) as f:
    config_data = yaml.safe_load(f)

config: Config = class_schema(Config)().load(config_data)
