from django import forms

from src.games.signals import (
    category_approved,
    category_declined,
    subcategory_approved,
    subcategory_declined,
)
from src.games.signals_definition import game_approved
from src.store.models import Collection, Status
from src.store.services.ipfs import send_to_ipfs
from src.store.signals import collection_approved, collection_declined

from .models import GameCategory, GameCompany, GameSubCategory


class GameCompanyForm(forms.ModelForm):
    set_avatar = forms.FileField(required=False)
    set_banner = forms.FileField(required=False)

    def __init__(self, *args, **kwargs):
        super(GameCompanyForm, self).__init__(*args, **kwargs)
        self.fields["description"].widget = forms.Textarea()

    class Meta:
        model = GameCompany
        fields = "__all__"

    def save(self, commit=True):
        set_avatar = self.cleaned_data.get("set_avatar", None)
        set_banner = self.cleaned_data.get("set_banner", None)
        if set_avatar:
            self.instance.avatar_ipfs = send_to_ipfs(set_avatar)
        if set_banner:
            self.instance.banner_ipfs = send_to_ipfs(set_banner)

        if self.instance.id:
            db_object = self.Meta.model.objects.get(id=self.instance.id)
            if (
                self.cleaned_data.get("is_approved") is not None
                and db_object.is_approved is None
            ):
                game_approved.send(
                    sender=self.Meta.model.__class__,
                    instance=self.instance,
                    approved=self.cleaned_data.get("is_approved"),
                )
        return super(GameCompanyForm, self).save(commit=commit)


class GameCategoryForm(forms.ModelForm):
    set_avatar = forms.ImageField(required=False)

    class Meta:
        model = GameCategory
        fields = "__all__"

    def save(self, commit=True):
        set_avatar = self.cleaned_data.get("set_avatar", None)
        if set_avatar:
            self.instance.avatar_ipfs = send_to_ipfs(set_avatar)
        if self.instance.id:
            db_object = self.Meta.model.objects.get(id=self.instance.id)
            if self.cleaned_data.get("is_approved") and db_object.is_approved is None:
                category_approved.send(
                    sender=self.Meta.model.__class__, instance=self.instance
                )
            elif (
                self.cleaned_data.get("is_approved") is False
                and db_object.is_approved is None
            ):
                category_declined.send(
                    sender=self.Meta.model.__class__, instance=self.instance
                )
        return super(GameCategoryForm, self).save(commit=commit)


class GameSubCategoryForm(forms.ModelForm):
    set_avatar = forms.ImageField(required=False)

    class Meta:
        model = GameSubCategory
        fields = "__all__"

    def save(self, commit=True):
        set_avatar = self.cleaned_data.get("set_avatar", None)
        if set_avatar:
            self.instance.avatar_ipfs = send_to_ipfs(set_avatar)

        if self.instance.id:
            db_object = self.Meta.model.objects.get(id=self.instance.id)
            if self.cleaned_data.get("is_approved") and db_object.is_approved is None:
                subcategory_approved.send(
                    sender=self.Meta.model.__class__, instance=self.instance
                )
            elif (
                self.cleaned_data.get("is_approved") is False
                and db_object.is_approved is None
            ):
                subcategory_declined.send(
                    sender=self.Meta.model.__class__, instance=self.instance
                )

        return super(GameSubCategoryForm, self).save(commit=commit)


class GameCategoryImageForm(forms.ModelForm):
    banner = forms.ImageField(required=False)

    def save(self, commit: bool = True):
        ipfs_image = self.cleaned_data.get("banner", None)
        if ipfs_image:
            self.instance.avatar_ipfs = send_to_ipfs(ipfs_image)
        return super(GameCategoryImageForm, self).save(commit=commit)

    class Meta:
        model = GameCategory
        fields = ("name", "banner")


class GameSubCategoryImageForm(GameCategoryImageForm):
    class Meta:
        model = GameSubCategory
        fields = ("name", "banner")


class GameCollectionForm(forms.ModelForm):
    approved = forms.BooleanField()

    class Meta:
        models = Collection
        fields = "__all__"

    def clean(self):
        if self.cleaned_data.get("approved"):
            self.instance.status = Status.COMMITTED
            self.instance.save()
            collection_approved.send(
                sender=self.Meta.model.__class__, instance=self.instance
            )

        elif self.cleaned_data.get("approved") is False:
            self.instance.delete()
            collection_declined.send(
                sender=self.Meta.model.__class__, instance=self.instance
            )

        return self.cleaned_data
