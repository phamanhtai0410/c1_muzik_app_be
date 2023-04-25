from django.contrib import admin

from .models import BidsHistory, TokenHistory, UserAction


class UserActionAdmin(admin.ModelAdmin):
    model = UserAction
    readonly_fields = ("id",)
    exclude = ("is_viewed",)
    list_display = ("user", "method", "date")
    list_filter = ("method",)
    ordering = ("-date",)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


class TokenHistoryAdmin(admin.ModelAdmin):
    model = TokenHistory
    exclude = ("is_viewed",)
    list_display = (
        "token",
        "amount",
        "new_owner",
        "old_owner",
        "method",
        "date",
        "price",
        "currency",
    )
    list_filter = ("method",)
    ordering = ("-date",)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


class BidsHistoryAdmin(admin.ModelAdmin):
    model = BidsHistory
    list_display = ("token", "user", "price", "date")
    ordering = ("-date",)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


admin.site.register(UserAction, UserActionAdmin)
admin.site.register(TokenHistory, TokenHistoryAdmin)
admin.site.register(BidsHistory, BidsHistoryAdmin)
