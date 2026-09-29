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
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
import yaml

DEFAULT_USER_SEGMENT = "Signed-in users"
DEFAULT_PERMISSION_GROUP = "Agents and admins"
EVERYONE = "everyone"
LOCALE = "en-us"
UPLOAD_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 2

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
        """Upload one inline attachment.

        Zendesk answers 409 with an empty body when the upload lands right after
        the article was created (seen live 2026-09-29); the same call succeeds a
        moment later. Retry 409 only; every other error surfaces at once.
        """
        mime = MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")
        url_path = f"/help_center/articles/{article_id}/attachments.json"
        for attempt in range(1, UPLOAD_ATTEMPTS + 1):
            with path.open("rb") as handle:
                response = self.session.request(
                    "POST",
                    self.base + url_path,
                    files={"file": (path.name, handle, mime)},
                    data={"inline": "true"},
                )
            if response.status_code == 409 and attempt < UPLOAD_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS * attempt)
                continue
            if response.status_code >= 400:
                raise PublishError(
                    f"POST {url_path} returned {response.status_code} after "
                    f"{attempt} attempt(s): {response.text[:500]}"
                )
            return response.json()["article_attachment"]
        raise PublishError(f"POST {url_path}: exhausted {UPLOAD_ATTEMPTS} attempts")


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


def _is_local(src: str) -> bool:
    lowered = src.lower()
    return not lowered.startswith(("http://", "https://", "//", "data:", "/hc/"))


def local_images(html: str) -> list[str]:
    seen: list[str] = []
    for match in IMG_SRC_RE.finditer(html):
        src = match.group(2)
        if _is_local(src) and src not in seen:
            seen.append(src)
    return seen


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class AttachmentReport:
    uploaded: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)
    orphaned_ids: list[int] = field(default_factory=list)


def sync_attachments(
    client: ZendeskHelpCenter, article: Article, approved: frozenset[str]
) -> AttachmentReport:
    """Upload new or changed local images as inline attachments; reuse unchanged ones.

    `approved` is the set of relative paths the user confirmed through the PII
    gate. An image that needs uploading and is not in it stops the run.
    """
    if article.article_id is None:
        raise PublishError(
            "sync_attachments needs an article_id; create the draft first"
        )
    report = AttachmentReport()
    srcs = local_images(article.html)
    for src in srcs:
        if not (article.dir / src).is_file():
            raise PublishError(
                f"{src} is referenced in article.html but not found under {article.dir}"
            )
    for src in srcs:
        path = article.dir / src
        digest = sha256_of(path)
        entry = article.attachments.get(src)
        if entry and entry.get("sha256") == digest:
            report.reused.append(src)
            continue
        if src not in approved:
            raise PublishError(
                f"PII gate: {src} is new or changed and has not been approved for upload"
            )
        uploaded = client.upload_attachment(article.article_id, path)
        if entry:
            report.orphaned_ids.append(int(entry["id"]))
        article.attachments[src] = {
            "id": int(uploaded["id"]),
            "url": uploaded["content_url"],
            "sha256": digest,
        }
        report.uploaded.append(src)
    return report


def rewrite_srcs(html: str, attachments: dict[str, dict]) -> str:
    def swap(match: re.Match) -> str:
        src = match.group(2)
        entry = attachments.get(src)
        if entry is None:
            return match.group(0)
        return f"{match.group(1)}{entry['url']}{match.group(3)}"

    return IMG_SRC_RE.sub(swap, html)


def check_overwrite_guard(remote_article: dict, article: Article) -> None:
    """Abort when Zendesk changed since the last publish this folder knows about."""
    known = article.last_known_updated_at
    remote = remote_article.get("updated_at")
    if known is None:
        return
    if remote != known:
        raise PublishError(
            "Overwrite guard: the article changed in Zendesk since the last publish. "
            f"article.yml knows {known}; Zendesk reports {remote}. Someone edited it in the "
            "editor. Pull their change into article.html and update last_known_updated_at, "
            "or confirm the overwrite by setting last_known_updated_at to the Zendesk value."
        )


def backup_translation(translation: dict, backup_dir: Path, article: Article) -> Path:
    """Save the stored title and body before overwriting. Never inside the repo."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = re.sub(r"[^0-9]", "", translation.get("updated_at") or "") or "unknown"
    path = backup_dir / f"zendesk-article-{article.article_id}-{stamp}.html"
    path.write_text(
        f"<!-- title: {translation.get('title', '')} -->\n{translation.get('body', '')}"
    )
    return path


def verify_readback(translation: dict, article: Article) -> None:
    if translation.get("title") != article.title:
        raise PublishError(
            f"Read-back title mismatch: sent {article.title!r}, "
            f"stored {translation.get('title')!r}"
        )
    stored_ids = {
        int(i) for i in ATTACHMENT_ID_RE.findall(translation.get("body") or "")
    }
    expected_ids = {int(e["id"]) for e in article.attachments.values()}
    missing = sorted(expected_ids - stored_ids)
    if missing:
        raise PublishError(
            f"Read-back: attachment ids {missing} are not in the stored body"
        )


@dataclass
class PublishResult:
    article_id: int
    html_url: str
    draft: bool
    uploaded: list[str]
    reused: list[str]
    orphaned_ids: list[int]
    backup: Path | None


def publish(
    article_dir: Path,
    *,
    live: bool,
    approved_images: frozenset[str] = frozenset(),
    backup_dir: Path,
    client: ZendeskHelpCenter | None = None,
) -> PublishResult:
    """Create or update the article as a draft; go live only when `live` is True.

    Order: load and refuse early; resolve visibility; create draft or fetch and
    guard; back up; sync images; rewrite srcs in memory; PUT article fields;
    PUT translation; read back; save state.
    """
    article = load_article(article_dir)
    client = client or client_from_environment()
    segment_id, group_id = resolve_visibility(client, article)

    backup: Path | None = None
    if article.article_id is None:
        created = client.create_article(
            article.section_id,
            {
                "title": article.title,
                "body": "<p>Draft in progress.</p>",
                "locale": LOCALE,
                "draft": True,
                "author_id": article.author_id,
                "user_segment_id": segment_id,
                "permission_group_id": group_id,
                "label_names": article.labels,
            },
        )
        article.article_id = int(created["id"])
        save_state(article)  # a later failure must not create a duplicate on re-run
        remote = created
    else:
        remote = client.get_article(article.article_id)
        check_overwrite_guard(remote, article)
        backup = backup_translation(
            client.get_translation(article.article_id), backup_dir, article
        )

    report = sync_attachments(client, article, approved_images)
    body = rewrite_srcs(article.html, article.attachments)

    remote = client.update_article(
        article.article_id,
        {
            "author_id": article.author_id,
            "user_segment_id": segment_id,
            "permission_group_id": group_id,
            "label_names": article.labels,
        },
    )
    client.update_translation(
        article.article_id, {"title": article.title, "body": body, "draft": not live}
    )
    stored = client.get_translation(article.article_id)
    verify_readback(stored, article)

    # The translation PUT changes updated_at after the article PUT returned.
    article.last_known_updated_at = client.get_article(article.article_id)["updated_at"]
    save_state(article)
    return PublishResult(
        article_id=article.article_id,
        html_url=str(remote.get("html_url", "")),
        draft=not live,
        uploaded=report.uploaded,
        reused=report.reused,
        orphaned_ids=report.orphaned_ids,
        backup=backup,
    )
