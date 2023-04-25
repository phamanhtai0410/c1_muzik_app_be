from dataclasses import dataclass


@dataclass
class DeployData:
    collection_name: str
    address: str
    deploy_block: int
    tx_hash: str


@dataclass
class BuyData:
    buyer: str
    seller: str
    price: float
    amount: int
    token_id: int
    tx_hash: str
    currency_address: str
    collection_address: str


@dataclass
class MintData:
    internal_id: int
    mint_id: int
    owner: str
    tx_hash: str
    amount: int


@dataclass
class TransferData:
    token_id: int
    new_owner: str
    old_owner: str
    tx_hash: str
    amount: int


@dataclass
class PromotionData:
    package: int
    collection_address: str
    token_id: str
    buyer: str
    chain_id: int


@dataclass
class ApprovalData:
    account: str
    operator: str
    is_approved: bool
