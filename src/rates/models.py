from django.db import models

from src.consts import MAX_AMOUNT_LEN


class UsdRate(models.Model):
    """
    Absolutely typical rate app for winter 2021.
    """

    rate = models.DecimalField(
        max_digits=MAX_AMOUNT_LEN, decimal_places=8, blank=True, null=True, default=None
    )
    coin_node = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20, blank=True, null=True, default=None)
    name = models.CharField(max_length=100, blank=True, null=True, default=None)
    image = models.CharField(max_length=500, null=True, blank=True, default=None)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    address = models.CharField(max_length=128, blank=True, null=True, default=None)
    decimal = models.PositiveSmallIntegerField(null=True, blank=True, default=None)
    network = models.ForeignKey(
        "networks.Network",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        default=None,
        related_name="currencies",
    )

    def __str__(self):
        return self.symbol

    @property
    def get_decimals(self):
        return 10 ** self.decimal

    @property
    def service_fee(self):
        return self.network.platform_fee_percentage

    @property
    def fee_address(self):
        return self.network.platform_fee_address

    def set_decimals(self) -> None:
        self.decimal = self.network.contract_call(
            method_type="read",
            contract_type="token",
            address=self.address,
            function_name="decimals",
            input_params=(),
            input_type=(),
            output_types=("uint8",),
        )
        self.save()
