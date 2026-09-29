"""Publish a help article folder to the Zendesk Help Center.

Runs only under pytest: the session fixture in tests/conftest.py loads
ZENDESK_SUBDOMAIN, ZENDESK_EMAIL and ZENDESK_TOKEN from 1Password. See
.claude/skills/zendesk-help-articles/SKILL.md for the flow and
references/zendesk-api.md for the endpoints.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests
import yaml

DEFAULT_USER_SEGMENT = "Signed-in users"
DEFAULT_PERMISSION_GROUP = "Agents and admins"
EVERYONE = "everyone"
LOCALE = "en-us"

IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', re.IGNORECASE)
ATTACHMENT_ID_RE = re.compile(r"/hc/article_attachments/(\d+)")


class PublishError(Exception):
    """A refusal or a failed API call. The message is meant for the user."""


@dataclass
class Article:
    dir: Path
    title: str
    section_id: int
    author_id: int
    user_segment: str
    permission_group: str
    labels: list[str]
    article_id: int | None
    last_known_updated_at: str | None
    attachments: dict[str, dict]
    html: str
    _raw: dict = field(default_factory=dict, repr=False)


def load_article(article_dir: Path) -> Article:
    yml = article_dir / "article.yml"
    html_path = article_dir / "article.html"
    if not yml.exists():
        raise PublishError(f"{yml} not found")
    if not html_path.exists():
        raise PublishError(f"{html_path} not found")
    raw = yaml.safe_load(yml.read_text()) or {}
    for key in ("title", "section_id", "author_id"):
        if not raw.get(key):
            raise PublishError(f"article.yml is missing `{key}`; refusing to publish")
    return Article(
        dir=article_dir,
        title=str(raw["title"]),
        section_id=int(raw["section_id"]),
        author_id=int(raw["author_id"]),
        user_segment=str(raw.get("user_segment") or DEFAULT_USER_SEGMENT),
        permission_group=str(raw.get("permission_group") or DEFAULT_PERMISSION_GROUP),
        labels=list(raw.get("labels") or []),
        article_id=int(raw["article_id"]) if raw.get("article_id") else None,
        last_known_updated_at=raw.get("last_known_updated_at"),
        attachments=dict(raw.get("attachments") or {}),
        html=html_path.read_text(),
        _raw=raw,
    )


def save_state(article: Article) -> None:
    """Write publish state back to article.yml, keeping every user-authored field."""
    out = dict(article._raw)
    out["article_id"] = article.article_id
    out["last_known_updated_at"] = article.last_known_updated_at
    out["attachments"] = article.attachments
    (article.dir / "article.yml").write_text(yaml.safe_dump(out, sort_keys=False))


MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
}


class ZendeskHelpCenter:
    """Thin wrapper over the Help Center REST API. Every method returns the unwrapped object."""

    def __init__(self, subdomain: str, email: str, token: str, session=None):
        self.base = f"https://{subdomain}.zendesk.com/api/v2"
        self.session = session or requests.Session()
        self.session.auth = (f"{email}/token", token)

    def _call(self, method: str, path: str, **kwargs) -> dict:
        response = self.session.request(method, self.base + path, **kwargs)
        if response.status_code >= 400:
            raise PublishError(
                f"{method} {path} returned {response.status_code}: {response.text[:500]}"
            )
        return response.json()

    def user_segments(self) -> list[dict]:
        return self._call("GET", "/help_center/user_segments.json")["user_segments"]

    def permission_groups(self) -> list[dict]:
        return self._call("GET", "/guide/permission_groups.json")["permission_groups"]

    def create_article(self, section_id: int, article: dict) -> dict:
        return self._call(
            "POST",
            f"/help_center/sections/{section_id}/articles.json",
            json={"article": article, "notify_subscribers": False},
        )["article"]

    def get_article(self, article_id: int) -> dict:
        return self._call("GET", f"/help_center/articles/{article_id}.json")["article"]

    def update_article(self, article_id: int, article: dict) -> dict:
        return self._call(
            "PUT", f"/help_center/articles/{article_id}.json", json={"article": article}
        )["article"]

    def get_translation(self, article_id: int) -> dict:
        return self._call(
            "GET", f"/help_center/articles/{article_id}/translations/{LOCALE}.json"
        )["translation"]

    def update_translation(self, article_id: int, translation: dict) -> dict:
        return self._call(
            "PUT",
            f"/help_center/articles/{article_id}/translations/{LOCALE}.json",
            json={"translation": translation},
        )["translation"]

    def upload_attachment(self, article_id: int, path: Path) -> dict:
        mime = MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")
        with path.open("rb") as handle:
            return self._call(
                "POST",
                f"/help_center/articles/{article_id}/attachments.json",
                files={"file": (path.name, handle, mime)},
                data={"inline": "true"},
            )["article_attachment"]


def client_from_environment() -> ZendeskHelpCenter:
    values = {}
    for name in ("ZENDESK_SUBDOMAIN", "ZENDESK_EMAIL", "ZENDESK_TOKEN"):
        value = os.environ.get(name)
        if not value:
            raise PublishError(
                f"{name} is not set. Run through `uv run pytest tests/test_zz_*.py -s` so "
                "tests/conftest.py loads it; a bare `uv run python` gets no secrets."
            )
        values[name] = value
    return ZendeskHelpCenter(
        values["ZENDESK_SUBDOMAIN"], values["ZENDESK_EMAIL"], values["ZENDESK_TOKEN"]
    )


def _id_by_name(items: list[dict], name: str, kind: str) -> int:
    for item in items:
        if item.get("name") == name:
            return int(item["id"])
    choices = ", ".join(sorted(str(i.get("name")) for i in items))
    raise PublishError(f"No {kind} named {name!r} in Zendesk. Available: {choices}")


def resolve_visibility(
    client: ZendeskHelpCenter, article: Article
) -> tuple[int | None, int]:
    """Map the names in article.yml to ids. Everyone only via the literal `everyone`."""
    if article.user_segment == EVERYONE:
        segment_id = None
    else:
        segment_id = _id_by_name(
            client.user_segments(), article.user_segment, "user segment"
        )
    group_id = _id_by_name(
        client.permission_groups(), article.permission_group, "permission group"
    )
    return segment_id, group_id
