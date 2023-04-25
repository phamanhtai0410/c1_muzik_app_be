from scanners.base import ScannerABC
from scanners.mixins.approval import ApprovalMixin
from scanners.mixins.buy import BuyMixin
from scanners.mixins.deploy import DeployMixin
from scanners.mixins.mint import MintMixin
from scanners.mixins.promotion import PromotionMixin
from scanners.mixins.transfers import TransferMixin


class Scanner(
    ScannerABC,
    DeployMixin,
    BuyMixin,
    TransferMixin,
    PromotionMixin,
    MintMixin,
    ApprovalMixin,
):
    EMPTY_ADDRESS = "0x0000000000000000000000000000000000000000"
