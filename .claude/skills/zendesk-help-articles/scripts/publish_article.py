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
