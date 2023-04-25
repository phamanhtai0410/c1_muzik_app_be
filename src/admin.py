from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

import markdown
from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path
from markupsafe import Markup

from src.settings import GUIDELINES_SECTIONS, config

if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


@dataclass
class Section:
    name: str
    url: str
    file_path: str

    @property
    def admin_url(self) -> str:
        return f"admin:{self.url}"


class CustomAdminSite(admin.AdminSite):
    index_template = "admin/custom_index.html"
    site_header = config.TITLE
    site_title = config.TITLE
    site_url = None
    index_title = "Administration"

    def index(
        self,
        request: "WSGIRequest",
        extra_context: dict = None,
    ) -> "CustomAdminSite":
        extra_context = {"sections": self.sections}
        return super(CustomAdminSite, self).index(request, extra_context)

    def get_urls(self) -> list:
        urls = super().get_urls()
        self._set_sections()
        custom_urls = self._get_guidelines_urls()
        return custom_urls + urls

    def _set_sections(self) -> None:
        self.sections = [Section(**section) for section in GUIDELINES_SECTIONS]

    def _get_guidelines_urls(self) -> list:
        guidelines_urls = list()
        for section in self.sections:
            func = self._get_template_func(section)
            guidelines_urls.append(path(f"{section.url}/", func, name=section.url))
        return guidelines_urls

    def _get_template_func(self, section: "Section") -> Callable[[Any], Any]:
        def template_func(request: "WSGIRequest") -> "TemplateResponse":
            with open(section.file_path, "r") as f:
                text = f.read()
                html = Markup(
                    markdown.markdown(text, extensions=["extra", "toc", "sane_lists"])
                )
            context = {
                "page_name": section.name,
                "html": html,
                "site_header": self.site_header,
                "site_title": self.site_title,
                "index_title": "Guidelines",
            }
            return TemplateResponse(request, "admin/guide_template.html", context)

        return template_func
