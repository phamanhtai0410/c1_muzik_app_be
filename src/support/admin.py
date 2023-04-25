from django.contrib import admin

from src.support.forms import SupportEmailForm
from src.support.models import Config, EmailConfig, EmailTemplate


class EmailConfigAdmin(admin.ModelAdmin):
    model = EmailConfig
    form = SupportEmailForm

    def has_add_permission(self, request):
        return self.model.objects.count() < 2

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        read_only_fields = []
        if obj:
            read_only_fields.append("role")
        if obj and obj.role.lower() == obj.EmailRole.RECEIVER.lower():
            read_only_fields.extend(["password", "smtp", "port", "use_tls"])
        return tuple(read_only_fields)


class ConfigAdmin(admin.ModelAdmin):
    model = Config
    readonly_fields = ["sales_volume", "sales_amount", "user_emails"]

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return not self.model.object()


class EmailTemplateAdmin(admin.ModelAdmin):
    model = EmailTemplate

    readonly_fields = ["hints"]
    exclude = ["message_type"]

    def has_add_permission(self, *args, **kwargs) -> bool:
        return self.model.objects.count() < len(self.model.MessageType.choices)

    def has_delete_permission(self, *args, **kwargs) -> bool:
        return False


admin.site.register(Config, ConfigAdmin)
admin.site.register(EmailConfig, EmailConfigAdmin)
admin.site.register(EmailTemplate, EmailTemplateAdmin)
