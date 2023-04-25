import base64
import uuid
from urllib.parse import urljoin

import filetype
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import models
from django_quill.fields import QuillField

from src.settings import ALLOWED_HOSTS


class SubscriptionUser(models.Model):
    email_address = models.EmailField(unique=True)

    def __str__(self):
        return self.email_address


class SubscriptionMail(models.Model):

    title = models.CharField(max_length=100, default="")
    text = QuillField(blank=True, null=True, default="")
    processed_text = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        return self.title

    def process_html(self):
        parsed_text = BeautifulSoup(self.text.html, features="html.parser")

        for image_tag in parsed_text.find_all("img"):
            base64_image = image_tag.get("src")
            header, data = base64_image.split(";base64,")
            decoded_file = base64.b64decode(data)
            image_file = ContentFile(decoded_file)

            extension = filetype.guess_extension(decoded_file)
            file_name = str(uuid.uuid4())[:12]
            full_name = f"{file_name}.{extension}"

            storage = FileSystemStorage()
            saved_image = storage.save(full_name, image_file)
            saved_image_url = storage.url(saved_image)
            absulute_uri = urljoin(f"https://{ALLOWED_HOSTS[0]}", saved_image_url)

            new_tag = parsed_text.new_tag("img")
            new_tag["src"] = absulute_uri

            image_tag.replace_with(new_tag)

        self.processed_text = parsed_text.prettify()
