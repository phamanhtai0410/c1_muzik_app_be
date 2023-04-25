from django import forms
from django.contrib import admin
from django.utils.safestring import mark_safe
from nested_inline.admin import NestedModelAdmin, NestedTabularInline

from src.store.models import Status
from src.store.services.ipfs import send_to_ipfs
from src.utilities import get_media_from_ipfs

from .forms import (
    GameCategoryForm,
    GameCategoryImageForm,
    GameCollectionForm,
    GameCompanyForm,
    GameSubCategoryForm,
    GameSubCategoryImageForm,
)
from .models import (
    DefaultGameAvatar,
    DefaultGameBanner,
    GameCategory,
    GameCollection,
    GameCompany,
    GameSubCategory,
)


class GameSubCategoryInline(NestedTabularInline):
    model = GameSubCategory
    fk_name = "category"
    form = GameSubCategoryImageForm
    extra = 0
    readonly_fields = ("avatar_preview", "addresses")

    def avatar_preview(self, obj) -> "str":
        if obj.avatar_ipfs:
            return mark_safe(
                '<img src="{0}" width="100" height="100" style="object-fit:contain" />'.format(
                    get_media_from_ipfs(obj.avatar_ipfs)
                )
            )
        else:
            return "(No image)"

    def has_add_permission(self, request, obj=None):
        return False


class GameCategoryInline(NestedTabularInline):
    model = GameCategory
    fk_name = "game"
    inlines = (GameSubCategoryInline,)
    form = GameCategoryImageForm
    extra = 0
    readonly_fields = ("avatar_preview",)

    def avatar_preview(self, obj) -> "str":
        if obj.avatar_ipfs:
            return mark_safe(
                '<img src="{0}" width="100" height="100" style="object-fit:contain" />'.format(
                    get_media_from_ipfs(obj.avatar_ipfs)
                )
            )
        else:
            return "(No image)"

    def has_add_permission(self, request, obj=None):
        return False


class GameCompanyAdmin(NestedModelAdmin):
    model = GameCompany
    form = GameCompanyForm
    inlines = [
        GameCategoryInline,
    ]
    list_display = (
        "name",
        "is_approved",
        "user",
        "network",
        "email",
        "validating_result",
    )
    list_filter = ("name", "is_approved")
    search_fields = [
        "name",
    ]

    def get_queryset(self, request):
        qs = super(GameCompanyAdmin, self).get_queryset(request)
        return qs.filter(validating_result__isnull=False)

    fields = (
        "validating_result",
        "is_approved",
        "name",
        "email",
        "network",
        "whitepaper_link",
        "avatar_preview",
        "set_avatar",
        "banner_preview",
        "set_banner",
        "description",
        "user",
        "website",
        "twitter",
        "instagram",
        "telegram",
        "facebook",
        "medium",
        "discord",
        "background_color",
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = [
            "user",
            "network",
            "avatar_ipfs",
            "banner_ipfs",
            "banner_preview",
            "avatar_preview",
            "validating_result",
        ]
        if obj.is_approved is not None:
            readonly_fields.append("is_approved")
        return readonly_fields

    def avatar_preview(self, obj):
        # ex. the name of column is "image"
        if obj.avatar_ipfs:
            return mark_safe(
                '<img src="{0}" width="400" height="400" style="object-fit:contain" />'.format(
                    get_media_from_ipfs(obj.avatar_ipfs)
                )
            )
        else:
            return "(No image)"

    def banner_preview(self, obj):
        # ex. the name of column is "image"
        if obj.banner_ipfs:
            return mark_safe(
                '<img src="{0}" width="400" height="400" style="object-fit:contain" />'.format(
                    get_media_from_ipfs(obj.banner_ipfs)
                )
            )
        else:
            return "(No image)"

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class GameCategoryAdmin(NestedModelAdmin):
    model = GameCategory
    form = GameCategoryForm
    inlines = [
        GameSubCategoryInline,
    ]
    list_display = ("game", "name", "is_approved")
    list_filter = ("name", "is_approved")
    search_fields = [
        "name",
    ]

    def get_queryset(self, request):
        qs = super(GameCategoryAdmin, self).get_queryset(request)
        return qs.filter(
            is_approved__isnull=True,
            game__is_approved=True,
            game__validating_result__isnull=False,
        )

    fields = (
        "game",
        "name",
        "is_approved",
        "avatar_preview",
        "set_avatar",
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = [
            "game",
            "avatar_ipfs",
            "avatar_preview",
        ]
        if obj.is_approved is not None:
            readonly_fields.append("is_approved")
        return readonly_fields

    def avatar_preview(self, obj):
        # ex. the name of column is "image"
        if obj.avatar_ipfs:
            return mark_safe(
                '<img src="{0}" width="400" height="400" style="object-fit:contain" />'.format(
                    get_media_from_ipfs(obj.avatar_ipfs)
                )
            )
        else:
            return "(No image)"

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class GameSubCategoryAdmin(NestedModelAdmin):
    model = GameSubCategory
    form = GameSubCategoryForm

    inlines = []
    list_display = ("category", "name", "is_approved")
    list_filter = ("name", "is_approved")
    search_fields = [
        "name",
    ]

    fields = (
        "game",
        "name",
        "is_approved",
        "avatar_preview",
        "set_avatar",
    )

    def get_queryset(self, request):
        qs = super(GameSubCategoryAdmin, self).get_queryset(request)
        return qs.filter(
            is_approved__isnull=True,
            category__game__is_approved=True,
            category__is_approved=True,
            category__game__validating_result__isnull=False,
        )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = [
            "game",
            "avatar_ipfs",
            "avatar_preview",
        ]
        if obj.is_approved is not None:
            readonly_fields.append("is_approved")
        return readonly_fields

    def avatar_preview(self, obj):
        # ex. the name of column is "image"
        if obj.avatar_ipfs:
            return mark_safe(
                '<img src="{0}" width="400" height="400" style="object-fit:contain" />'.format(
                    get_media_from_ipfs(obj.avatar_ipfs)
                )
            )
        else:
            return "(No image)"

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class GameCollectionAdmin(admin.ModelAdmin):
    model = GameCollection
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
        "game_subcategory",
    )
    list_display = ("name", "address", "standard", "get_network", "deleted")
    list_filter = ("standard", "deleted")
    search_fields = [
        "name",
    ]
    form = GameCollectionForm

    exclude = (
        "cover_ipfs",
        "short_url",
        "deploy_block",
        "tags",
        "avatar_ipfs",
        "is_default",
        "deleted",
        "description",
        "id",
        "status",
        "creator_royalty",
        "site",
        "discord",
        "twitter",
        "instagram",
        "medium",
        "telegram",
        "is_imported",
    )

    def get_network(self, obj):
        return obj.network.name

    def get_queryset(self, request):
        qs = super(GameCollectionAdmin, self).get_queryset(request)
        return qs.filter(
            status=Status.PENDING,
            is_imported=True,
            game_subcategory__is_approved=True,
            game_subcategory__category__game__validating_result__isnull=False,
        )

    get_network.short_description = "Network"
    get_network.admin_order_field = "collection__network__name"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class DefaultGameAvatarForm(forms.ModelForm):
    avatar = forms.ImageField()

    def save(self, commit=True):
        avatar = self.cleaned_data.get("avatar", None)
        image = send_to_ipfs(avatar)
        self.instance.image = image
        return super(DefaultGameAvatarForm, self).save(commit=commit)

    class Meta:
        model = DefaultGameAvatar
        fields = "__all__"


class DefaultGameAvatarAdmin(admin.ModelAdmin):
    form = DefaultGameAvatarForm
    list_display = ("image",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "avatar",
                    "image",
                    "avatar_preview",
                ),
            },
        ),
    )
    readonly_fields = ("avatar_preview",)

    def avatar_preview(self, obj):
        if obj.image:
            return mark_safe(
                '<img src="{0}" width="400" height="400" style="object-fit:contain" />'.format(
                    obj.ipfs_image
                )
            )
        return "(No image)"

    avatar_preview.short_description = "Preview"


class DefaultGameBannerForm(forms.ModelForm):
    banner = forms.ImageField()

    def save(self, commit=True):
        banner = self.cleaned_data.get("banner", None)
        image = send_to_ipfs(banner)
        self.instance.image = image
        return super(DefaultGameBannerForm, self).save(commit=commit)

    class Meta:
        model = DefaultGameBanner
        fields = "__all__"


class DefaultGameBannerAdmin(admin.ModelAdmin):
    form = DefaultGameBannerForm
    list_display = ("image",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "banner",
                    "image",
                    "banner_preview",
                ),
            },
        ),
    )
    readonly_fields = ("banner_preview",)

    def banner_preview(self, obj):
        if obj.image:
            return mark_safe(
                '<img src="{0}" width="400" height="400" style="object-fit:contain" />'.format(
                    obj.ipfs_image
                )
            )
        return "(No image)"

    banner_preview.short_description = "Preview"


admin.site.register(GameCompany, GameCompanyAdmin)
admin.site.register(GameCategory, GameCategoryAdmin)
admin.site.register(GameSubCategory, GameSubCategoryAdmin)
admin.site.register(GameCollection, GameCollectionAdmin)
admin.site.register(DefaultGameAvatar, DefaultGameAvatarAdmin)
admin.site.register(DefaultGameBanner, DefaultGameBannerAdmin)
