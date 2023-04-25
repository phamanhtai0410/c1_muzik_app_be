from knox.models import AuthToken
from mixer.backend.django import mixer
from rest_framework.test import APIClient


class Client(APIClient):
    def __init__(self, is_authenticated=False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if is_authenticated:
            self.auth()

    def auth(self):
        self.user = mixer.blend("accounts.AdvUser", display_name="Rodion")
        _, token = AuthToken.objects.create(user=self.user)
        self.credentials(HTTP_AUTHORIZATION=f"Token {token}")
