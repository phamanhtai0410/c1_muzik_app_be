from django.contrib import admin

from src.promotion.models import Promotion, PromotionOptions, PromotionSettings


class PromotionInline(admin.TabularInline):
    model = PromotionOptions
    extra = 0
    exclude = ["pk", "package"]


@admin.register(PromotionSettings)
class PromotionSettingsAdmin(admin.ModelAdmin):
    inlines = [PromotionInline]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_filter = ("status",)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False
