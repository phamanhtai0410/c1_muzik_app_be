from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group
from django.utils.safestring import mark_safe
from knox.models import AuthToken

from src.accounts.models import AdvUser, DefaultAvatar
from src.store.services.ipfs import send_to_ipfs


class DefaultAvatarForm(forms.ModelForm):
    avatar = forms.ImageField()

    def save(self, commit=True):
        avatar = self.cleaned_data.get("avatar", None)
        image = send_to_ipfs(avatar)
        self.instance.image = image
        return super(DefaultAvatarForm, self).save(commit=commit)

    class Meta:
        model = DefaultAvatar
        fields = "__all__"


class DefaultAvatarAdmin(admin.ModelAdmin):
    form = DefaultAvatarForm
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


class UserAvatarForm(forms.ModelForm):
    avatar = forms.ImageField(required=False)

    def save(self, commit=True):
        avatar = self.cleaned_data.get("avatar", None)
        if avatar:
            image = send_to_ipfs(avatar)
            self.instance.avatar_ipfs = image
        return super(UserAvatarForm, self).save(commit=commit)

    class Meta:
        model = AdvUser
        fields = "__all__"


class AdvUserAdmin(admin.ModelAdmin):
    model = AdvUser
    form = UserAvatarForm
    readonly_fields = ("id", "date_joined", "last_login", "username", "avatar_ipfs")
    list_display = ("username", "display_name")
    exclude = (
        "is_superuser",
        "first_name",
        "is_staff",
        "groups",
        "last_name",
        "user_permissions",
        "password",
        "is_verificated",
        "cover_ipfs",
        "custom_url",
        "metamask_message",
        "facebook",
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


admin.site.register(AdvUser, AdvUserAdmin)
admin.site.register(DefaultAvatar, DefaultAvatarAdmin)
admin.site.unregister(Group)
admin.site.unregister(SocialToken)
admin.site.unregister(SocialAccount)
admin.site.unregister(SocialApp)
admin.site.unregister(EmailAddress)
admin.site.unregister(AuthToken)
