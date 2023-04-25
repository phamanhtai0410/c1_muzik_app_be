from django.db.models.signals import post_save
from django.dispatch import receiver

from src.promotion.models import PromotionOptions


@receiver(post_save, sender=PromotionOptions)
def set_promotion_package_number(
    sender, instance: PromotionOptions, *args, **kwargs
) -> None:
    """
    set unique package identifier for contract interaction.
    Due to "uint8" type restricting to 256 values, deleted numbers are reused for new packages.
    """
    if instance.package is None:
        occupied = PromotionOptions.objects.exclude(package__isnull=True).order_by(
            "package"
        )
        occupied_list = occupied.values_list("package", flat=True)
        occupied_last = occupied.last().package if occupied else 0
        for i in range(1, occupied_last + 2):
            if i not in occupied_list:
                instance.package = i
                instance.save(update_fields=("package",))
                break
