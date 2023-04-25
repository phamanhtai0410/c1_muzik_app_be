from django.db import models

from src.consts import MAX_AMOUNT_LEN


class PromotionSettings(models.Model):
    slots = models.PositiveIntegerField()
    network = models.ForeignKey(
        "networks.Network", unique=True, on_delete=models.CASCADE
    )

    class Meta:
        verbose_name_plural = "Promotion Settings"

    def __str__(self) -> str:
        return self.network.name

    @property
    def available_slots(self):
        occupied = (
            Promotion.objects.filter(network=self.network)
            .exclude(status=Promotion.PromotionStatus.FINISHED)
            .distinct("token").count()
        )
        return max(self.slots - occupied, 0)


class PromotionOptions(models.Model):
    promotion = models.ForeignKey(
        "PromotionSettings", on_delete=models.CASCADE, related_name="options"
    )
    days = models.PositiveIntegerField()
    usd_price = models.DecimalField(max_digits=MAX_AMOUNT_LEN, decimal_places=2)
    package = models.PositiveIntegerField(null=True, unique=True)

    class Meta:
        verbose_name_plural = "Promotion Data"

    def __str__(self) -> str:
        return ""


class Promotion(models.Model):
    class PromotionStatus(models.TextChoices):
        WAITING = "Waiting list"
        IN_PROGRESS = "In progress"
        FINISHED = "Finished"

    token = models.ForeignKey(
        "store.Token", on_delete=models.CASCADE, related_name="promotions"
    )
    owner = models.ForeignKey(
        "store.Ownership", on_delete=models.CASCADE, related_name="promotions"
    )
    network = models.ForeignKey("networks.Network", on_delete=models.CASCADE)
    valid_until = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True)
    status = models.CharField(max_length=20, choices=PromotionStatus.choices)

    def __str__(self) -> str:
        return f"{self.token.name}"
