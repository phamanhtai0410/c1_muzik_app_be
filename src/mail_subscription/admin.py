from django.contrib import admin

from src.mail_subscription.models import SubscriptionMail


class SubscribeMailAdmin(admin.ModelAdmin):
    model = SubscriptionMail
    readonly_fields = ("processed_text",)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(SubscriptionMail, SubscribeMailAdmin)
