from django import forms
from django.contrib import admin
from django.contrib.sites.models import Site
from django.db import models
from django.forms import CheckboxSelectMultiple, ModelForm
from django.utils.safestring import mark_safe
from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    SolarSchedule,
)

from src.store.models import Bid, Category, Collection, Ownership, Tags, Token
from src.store.services.ipfs import send_to_ipfs
from src.store.signals import (
    collection_approved,
    collection_declined,
    collection_restored,
)


class CategoryForm(forms.ModelForm):
    set_image = forms.FileField(required=False)
    set_banner = forms.FileField(required=False)

    def save(self, commit=True):
        set_image = self.cleaned_data.get("set_image", None)
        set_banner = self.cleaned_data.get("set_banner", None)
        if set_image:
            icon = send_to_ipfs(set_image)
            self.instance.image = icon
        if set_banner:
            banner = send_to_ipfs(set_banner)
            self.instance.banner = banner
        return super(CategoryForm, self).save(commit=commit)

    class Meta:
        model = Category
        fields = "__all__"


class CategoryAdmin(admin.ModelAdmin):
    form = CategoryForm
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "image",
                    "banner",
                    "set_image",
                    "set_banner",
                ),
            },
        ),
    )
    readonly_fields = ("image", "banner")


class TagForm(forms.ModelForm):
    set_image = forms.FileField(required=False)
    set_banner = forms.FileField(required=False)

    def save(self, commit=True):
        set_image = self.cleaned_data.get("set_image", None)
        set_banner = self.cleaned_data.get("set_banner", None)
        if set_image:
            icon = send_to_ipfs(set_image)
            self.instance.image = icon
        if set_banner:
            banner = send_to_ipfs(set_banner)
            self.instance.banner = banner
        return super(TagForm, self).save(commit=commit)

    class Meta:
        model = Tags
        exclude = ("category",)


class TagAdmin(admin.ModelAdmin):
    form = TagForm
    list_display = ("name",)
    list_filter = ("category",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    # "category",
                    "name",
                    "image",
                    "banner",
                    "set_image",
                    "set_banner",
                    "description",
                ),
            },
        ),
    )


class TokenStandardFilter(admin.SimpleListFilter):
    title = "token standard"
    parameter_name = "token_standard"

    def lookups(self, request, model_admin):
        return (
            ("ERC721", "ERC721"),
            ("ERC1155", "ERC1155"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "ERC721":
            return queryset.filter(collection__standard="ERC721")
        elif value == "ERC1155":
            return queryset.filter(collection__standard="ERC1155")
        return queryset


class BidAdmin(admin.ModelAdmin):
    model = Bid
    list_display = ("token", "user")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


class TokenForm(forms.ModelForm):
    def clean(self):
        data = self.cleaned_data
        if not data.get("deleted") and self.instance.collection.deleted:
            raise forms.ValidationError("Can't restore token in deleted collection.")
        return self.cleaned_data


class TokenAdmin(admin.ModelAdmin):
    model = Token
    form = TokenForm
    readonly_fields = (
        "id",
        "image_preview",
        "created_at",
        "total_supply",
        "format",
        "collection",
        "name",
        "tx_hash",
        "ipfs",
        "image",
        "animation_file",
        "creator",
        "internal_id",
        "properties",
        "status",
        "description",
        "category",
        "mint_id",
    )
    formfield_overrides = {
        models.ManyToManyField: {"widget": CheckboxSelectMultiple},
    }

    def image_preview(self, obj):
        # ex. the name of column is "image"
        if obj.ipfs or obj.image:
            return mark_safe(
                '<img src="{0}" width="400" height="400" style="object-fit:contain" />'.format(
                    obj.media
                )
            )
        else:
            return "(No image)"

    image_preview.short_description = "Preview"
    list_display = (
        "name",
        "collection",
        "status",
        "standard",
        "get_network",
        "deleted",
    )
    list_filter = (
        "collection__name",
        TokenStandardFilter,
        "status",
        "deleted",
    )
    search_fields = [
        "name",
    ]

    exclude = (
        "creator_royalty",
        "is_favorite",
        "digital_key",
        "external_link",
        "tags",
        "_properties",
    )

    def get_network(self, obj):
        return obj.collection.network.name

    get_network.short_description = "Network"
    get_network.admin_order_field = "collection__network__name"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CollectionForm(ModelForm):
    set_image = forms.ImageField(required=False)

    class Meta:
        models = Collection
        fields = "__all__"

    def clean(self):
        data = self.cleaned_data
        standard = data.get("standard") or self.instance.standard
        network = data.get("network") or self.instance.network
        name = data.get("name") or self.instance.name
        already_exists = (
            Collection.objects.network(network)
            .filter(is_default=True, standard=standard)
            .exclude(name=name)
        )
        if data.get("is_default") and already_exists.exists():
            raise forms.ValidationError(
                f"There can be only one default {standard} collection for network {network}"
            )
        return self.cleaned_data

    def save(self, commit=True):
        set_image = self.cleaned_data.get("set_image", None)
        if set_image:
            icon = send_to_ipfs(set_image)
            self.instance.avatar_ipfs = icon
        if self.instance.id:
            db_object = Collection.objects.get(id=self.instance.id)
            if self.cleaned_data.get("deleted") is False and db_object.deleted is True:
                collection_restored.send(
                    sender=self.Meta.model.__class__, instance=self.instance
                )
            if self.cleaned_data.get("is_approved") and db_object.is_approved is None:
                collection_approved.send(
                    sender=self.model.__class__, instance=self.instance
                )
            elif (
                self.cleaned_data.get("is_approved") is False
                and db_object.is_approved is None
            ):
                collection_declined.send(
                    sender=self.model.__class__, instance=self.instance
                )
        return super(CollectionForm, self).save(commit=commit)


class CollectionAdmin(admin.ModelAdmin):
    model = Collection
    readonly_fields = (
        "id",
        "name",
        "address",
        "symbol",
        "standard",
        "creator",
        "status",
        "network",
        "creator_royalty",
        "image_preview",
        "game_subcategory",
    )
    list_display = ("name", "address", "standard", "status", "get_network", "deleted")
    list_filter = ("standard", "deleted")
    search_fields = [
        "name",
    ]
    form = CollectionForm

    exclude = (
        "cover_ipfs",
        "short_url",
        "deploy_block",
        "tags",
        "avatar_ipfs",
        "is_imported",
    )

    def image_preview(self, obj):
        # ex. the name of column is "image"
        if obj.avatar:
            return mark_safe(
                '<img src="{0}" width="400" height="400" style="object-fit:contain" />'.format(
                    obj.avatar
                )
            )
        else:
            return "(No image)"

    def get_network(self, obj):
        return obj.network.name

    get_network.short_description = "Network"
    get_network.admin_order_field = "collection__network__name"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OwnershipAdmin(admin.ModelAdmin):
    model = Ownership
    list_display = ("token", "owner", "quantity")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


# admin.site.register(Tags, TagAdmin)
admin.site.register(Ownership, OwnershipAdmin)
admin.site.register(Token, TokenAdmin)
admin.site.register(Bid, BidAdmin)
admin.site.register(Collection, CollectionAdmin)
admin.site.register(Category, CategoryAdmin)

admin.site.unregister(SolarSchedule)
admin.site.unregister(ClockedSchedule)
admin.site.unregister(PeriodicTask)
admin.site.unregister(IntervalSchedule)
admin.site.unregister(CrontabSchedule)

admin.site.unregister(Site)
