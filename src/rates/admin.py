from django.contrib import admin

from src.rates.models import UsdRate


class UsdRateAdmin(admin.ModelAdmin):
    model = UsdRate
    list_display = ("name", "symbol", "rate", "network")
    list_filter = ("coin_node", "network")

    def has_delete_permission(self, request, obj=None):
        return None

    def has_add_permission(self, request):
        return None

    def has_change_permission(self, request, obj=None):
        return None


admin.site.register(UsdRate, UsdRateAdmin)
