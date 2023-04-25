from django import forms
from django.contrib import admin
from django_admin_inline_paginator.admin import TabularInlinePaginated

from src.networks.models import Network, Provider
from src.store.services.ipfs import send_to_ipfs


class ProviderInline(TabularInlinePaginated):
    model = Provider
    extra = 0


class NetworkIconForm(forms.ModelForm):
    set_icon = forms.FileField(required=False)

    def save(self, commit=True):
        set_icon = self.cleaned_data.get("set_icon", None)
        if set_icon:
            icon = send_to_ipfs(set_icon)
            self.instance.icon = icon
        return super(NetworkIconForm, self).save(commit=commit)

    class Meta:
        model = Network
        fields = "__all__"


class NetworkAdmin(admin.ModelAdmin):
    form = NetworkIconForm
    inlines = (ProviderInline,)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "native_symbol",
                    "needs_middleware",
                    "fabric721_address",
                    "fabric1155_address",
                    "exchange_address",
                    "promotion_address",
                    "platform_fee_address",
                    "platform_fee_percentage",
                    "network_type",
                    "deadline",
                    "auction_timeout",
                    "daily_import_requests",
                ),
            },
        ),
    )


admin.site.register(Network, NetworkAdmin)
