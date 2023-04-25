from django import forms
from django.core.mail import send_mail
from django.forms import ValidationError

from src.support.models import EmailConfig


class SupportEmailForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False)

    class Meta:
        model = EmailConfig
        fields = ("role", "address", "password", "smtp", "port", "use_tls")

    def clean(self) -> None:
        role = self.instance.role or self.cleaned_data.get("role")
        not_first = (
            self.Meta.model.objects.filter(role=role)
            .exclude(id=self.instance.id)
            .count()
            > 0
        )
        if not_first:
            raise ValidationError("you can set only one email for each role")
        FIELDS = [
            "password",
            "smtp",
            "port",
            "use_tls",
        ]
        any_field_not_empty = any([self.cleaned_data.get(field) for field in FIELDS])
        if (
            self.instance.role == self.instance.EmailRole.RECEIVER
            or self.cleaned_data.get("role") == self.instance.EmailRole.RECEIVER
        ) and any_field_not_empty:
            raise ValidationError("receiver should have only address")

        all_fields_getting = all([self.cleaned_data.get(field) for field in FIELDS])
        if (
            self.instance.role == self.instance.EmailRole.SENDER
            or self.cleaned_data.get("role") == self.instance.EmailRole.SENDER
        ) and not all_fields_getting:
            raise ValidationError("sender should have all fields set")

        # if sender data changed, check credentials
        FIELDS.append("address")
        data_changed = any(
            [
                self.cleaned_data.get("field") != getattr(self.instance, field)
                for field in FIELDS
            ]
        )
        if (
            role.lower() == self.instance.EmailRole.SENDER.lower()
            and data_changed
            and not self.check_credentials()
        ):
            raise ValidationError(
                "Credentials are not valid, test email sending failed"
            )

        return self.cleaned_data

    def check_credentials(self):
        username = self.cleaned_data.get("address") or self.instance.address
        password = self.cleaned_data.get("password") or self.instance.password
        smtp = self.cleaned_data.get("smtp") or self.instance.smtp
        port = self.cleaned_data.get("port") or self.instance.port
        use_tls = self.cleaned_data.get("address") or self.instance.use_tls
        connection = self.instance.connection(
            username=username, password=password, smtp=smtp, port=port, use_tls=use_tls
        )
        try:
            send_mail(
                "Noreply test email",
                "Is is just test email to check if credentials are valid",
                username,
                [username],
                connection=connection,
            )
            return True
        except Exception:
            return False
