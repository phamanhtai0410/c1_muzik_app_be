import itertools
from typing import Dict

from django.core.files.uploadedfile import UploadedFile

from src.store.services.filetype_parser.formats import EXTENSIONS, MIMETYPES


class FiletypeParser:
    def __init__(self, media_files: Dict[str, UploadedFile]):
        self.media_files = media_files
        self.media = media_files.get("media")
        self.parsing_type = "mimetype" if self.media.content_type else "extension"

    def parse_by_mimetype(self):
        mimetype_data = self.media.content_type.split("/")
        mime_header = mimetype_data[0]
        mime_value = mimetype_data[1]

        if mime_header == "image" and mime_value not in MIMETYPES.get("image"):
            return "video"

        if mime_header == "application":
            if mime_value in MIMETYPES.get("application"):
                return "model"
            else:
                return None

        if mime_header in MIMETYPES.keys():
            return mime_header

        return None

    def parse_by_extension(self):
        media_extension = self.media.name.split(".")[-1].lower()
        for extension_type, extension_list in EXTENSIONS.items():
            if media_extension in extension_list:
                return extension_type

        return None

    def is_format_allowed(self):
        media_extension = self.media.name.split(".")[-1].lower()
        if media_extension.lower() in list(itertools.chain(*EXTENSIONS.values())):
            return True

    def parse(self):
        if not self.is_format_allowed():
            return None
        return getattr(self, f"parse_by_{self.parsing_type}")()
