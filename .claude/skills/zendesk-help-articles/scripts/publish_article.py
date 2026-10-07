"""Publish a help article working folder to the Zendesk Help Center.

Runs only under pytest: the session fixture in tests/conftest.py loads
ZENDESK_SUBDOMAIN, ZENDESK_EMAIL and ZENDESK_TOKEN from 1Password. The working
folder lives in the session scratchpad; every entry point refuses one inside
the checkout, because Help Center articles are gated and this repo is public.
See .claude/skills/zendesk-help-articles/SKILL.md for the flow and
references/zendesk-api.md for the endpoints.
"""

from __future__ import annotations

import mimetypes
import os
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import escape
from pathlib import Path

import requests
import yaml

DEFAULT_USER_SEGMENT = "Signed-in users"
DEFAULT_PERMISSION_GROUP = "Agents and admins"
EVERYONE = "everyone"
LOCALE = "en-us"
UPLOAD_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 2
TIMEOUT_SECONDS = 60
# scripts/ -> zendesk-help-articles/ -> skills/ -> .claude/ -> checkout root
REPO_ROOT = Path(__file__).resolve().parents[4]
SHELL_PATH = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "design-system"
    / "sample-article.html"
)
BODY_OPEN = '<div class="article-body">'
SIDE_OPEN = '<div class="hc-side">'
HC_TITLE_RE = re.compile(r'<h1 class="hc-title">.*?</h1>', re.DOTALL)

# Group 1: everything up to and including `src=`; group 2: the quote; group 3: the value.
# The lookbehind keeps `data-src=` from matching.
IMG_SRC_RE = re.compile(
    r"(<img\b[^>]*?(?<![-\w])src=)([\"'])([^\"']+)\2", re.IGNORECASE
)
# Full content_url, the shortened relative form, and the locale-prefixed form
# (/hc/en-us/article_attachments/<id>) that older articles may carry.
ATTACHMENT_ID_RE = re.compile(
    r"/hc/(?:[a-z]{2}(?:-[a-z]{2})?/)?article_attachments/(\d+)", re.IGNORECASE
)


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
    html: str
    _raw: dict = field(default_factory=dict, repr=False)


def _iso_z(value) -> str | None:
    """Normalize a timestamp to Zendesk's `YYYY-MM-DDTHH:MM:SSZ` string.

    yaml.safe_load turns an unquoted ISO timestamp into a datetime, and
    `datetime != str` is always true, which would trip the overwrite guard on
    every run after someone hand-edits the value.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_workdir(path: Path) -> None:
    """Refuse a folder inside the checkout. Articles are gated; the repo is public.

    Run from a worktree under .claude/worktrees/, REPO_ROOT is the worktree, so
    every ancestor holding a `.git` (the main checkout) is refused too.
    """
    resolved = path.resolve()
    roots = [REPO_ROOT, *(p for p in REPO_ROOT.parents if (p / ".git").exists())]
    for root in roots:
        if resolved.is_relative_to(root):
            raise PublishError(
                f"{path} is inside the checkout ({root}). Help Center articles are "
                "restricted to signed-in users and this repo is public, so the "
                "working folder must live in the session scratchpad."
            )


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
    labels = raw.get("labels") or []
    if isinstance(labels, str):
        labels = [labels]
    return Article(
        dir=article_dir,
        title=str(raw["title"]),
        section_id=int(raw["section_id"]),
        author_id=int(raw["author_id"]),
        user_segment=str(raw.get("user_segment") or DEFAULT_USER_SEGMENT),
        permission_group=str(raw.get("permission_group") or DEFAULT_PERMISSION_GROUP),
        labels=[str(label) for label in labels],
        article_id=int(raw["article_id"]) if raw.get("article_id") else None,
        last_known_updated_at=_iso_z(raw.get("last_known_updated_at")),
        html=html_path.read_text(),
        _raw=raw,
    )


def save_state(article: Article) -> None:
    """Write article_id and last_known_updated_at back, keeping every other field.

    Rewrites the whole file with yaml.safe_dump, so comments in article.yml do
    not survive a publish.
    """
    out = dict(article._raw)
    out["article_id"] = article.article_id
    out["last_known_updated_at"] = article.last_known_updated_at
    (article.dir / "article.yml").write_text(yaml.safe_dump(out, sort_keys=False))


def save_html(article: Article) -> None:
    (article.dir / "article.html").write_text(article.html)


class ZendeskHelpCenter:
    """Thin wrapper over the Help Center REST API. Every method returns the unwrapped object."""

    def __init__(self, subdomain: str, email: str, token: str, session=None):
        self.base = f"https://{subdomain}.zendesk.com/api/v2"
        self.session = session or requests.Session()
        self.session.auth = (f"{email}/token", token)

    def _call(self, method: str, path: str, **kwargs) -> dict:
        response = self.session.request(
            method, self.base + path, timeout=TIMEOUT_SECONDS, **kwargs
        )
        if response.status_code >= 400:
            raise PublishError(
                f"{method} {path} returned {response.status_code}: {response.text[:500]}"
            )
        return response.json()

    def _list(self, path: str, key: str) -> list[dict]:
        """Every item from a list endpoint, following next_page."""
        next_path: str | None = path
        items: list[dict] = []
        while next_path:
            page = self._call("GET", next_path)
            items.extend(page[key])
            next_page = page.get("next_page")
            next_path = next_page.removeprefix(self.base) if next_page else None
        return items

    def user_segments(self) -> list[dict]:
        return self._list("/help_center/user_segments.json", "user_segments")

    def permission_groups(self) -> list[dict]:
        return self._list("/guide/permission_groups.json", "permission_groups")

    def search_articles(self, query: str, limit: int = 10) -> list[dict]:
        return self._call(
            "GET",
            "/help_center/articles/search.json",
            params={"query": query, "per_page": max(1, min(int(limit), 100))},
        )["results"]

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

    def list_attachments(self, article_id: int) -> list[dict]:
        return self._list(
            f"/help_center/articles/{article_id}/attachments.json",
            "article_attachments",
        )

    def upload_attachment(self, article_id: int, path: Path) -> dict:
        """Upload one inline attachment.

        Zendesk answers 409 with an empty body when the upload lands right after
        the article was created (seen live 2026-09-29); the same call succeeds a
        moment later. Retry 409 only; every other error surfaces at once.
        """
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        url_path = f"/help_center/articles/{article_id}/attachments.json"
        attempt = 0
        while True:
            attempt += 1
            with path.open("rb") as handle:
                response = self.session.request(
                    "POST",
                    self.base + url_path,
                    files={"file": (path.name, handle, mime)},
                    data={"inline": "true"},
                    timeout=TIMEOUT_SECONDS,
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


def search_articles(
    query: str, limit: int = 10, client: ZendeskHelpCenter | None = None
) -> list[dict]:
    """Search the Help Center and print id, title, url, and updated date."""
    client = client or client_from_environment()
    results = client.search_articles(query, limit)
    for article in results:
        print(
            f"{article['id']}  {article['title']}\n"
            f"    {article['html_url']}  updated {article['updated_at']}"
        )
    if not results:
        print(f"No articles match {query!r}.")
    return results


def _id_by_name(items: list[dict], name: str, kind: str) -> int:
    for item in items:
        if item.get("name") == name:
            return int(item["id"])
    choices = ", ".join(sorted(str(i.get("name")) for i in items))
    raise PublishError(f"No {kind} named {name!r} in Zendesk. Available: {choices}")


def _name_by_id(items: list[dict], item_id: int, kind: str) -> str:
    for item in items:
        if int(item["id"]) == int(item_id):
            return str(item["name"])
    raise PublishError(f"No {kind} with id {item_id} in Zendesk")


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
    # Any root-relative src (/hc/, /guide-media/, //host) is already on Zendesk.
    return not lowered.startswith(("http://", "https://", "/", "data:"))


def local_images(html: str) -> list[str]:
    seen: list[str] = []
    for match in IMG_SRC_RE.finditer(html):
        src = match.group(3)
        if _is_local(src) and src not in seen:
            seen.append(src)
    return seen


def check_local_images(article: Article, approved: frozenset[str]) -> list[str]:
    """Validate every local image before any network call; return their srcs.

    Raises when a file is missing, sits outside the working folder, or is not
    in `approved` (the PII gate). An uploaded image's src is rewritten to its
    Zendesk url, so every local image is new and needs approval.
    """
    root = article.dir.resolve()
    srcs = local_images(article.html)
    for src in srcs:
        path = (article.dir / src).resolve()
        if not path.is_relative_to(root):
            raise PublishError(
                f"{src} resolves outside the working folder {article.dir}; "
                "images must live under images/"
            )
        if not path.is_file():
            raise PublishError(
                f"{src} is referenced in article.html but not found under {article.dir}"
            )
        if src not in approved:
            raise PublishError(
                f"PII gate: {src} is a new image and has not been approved for upload"
            )
    return srcs


def rewrite_srcs(html: str, urls: dict[str, str]) -> str:
    def swap(match: re.Match) -> str:
        url = urls.get(match.group(3))
        if url is None:
            return match.group(0)
        quote = match.group(2)
        return f"{match.group(1)}{quote}{url}{quote}"

    return IMG_SRC_RE.sub(swap, html)


def upload_local_images(
    client: ZendeskHelpCenter, article: Article, approved: frozenset[str]
) -> list[str]:
    """Upload each local image and point its src at the new attachment.

    article.html is rewritten on disk after every upload, so a failure midway
    leaves the uploaded images as Zendesk urls and a re-run skips them.
    """
    if article.article_id is None:
        raise PublishError(
            "upload_local_images needs an article_id; create the draft first"
        )
    uploaded: list[str] = []
    for src in check_local_images(article, approved):
        attachment = client.upload_attachment(article.article_id, article.dir / src)
        article.html = rewrite_srcs(article.html, {src: attachment["content_url"]})
        save_html(article)
        uploaded.append(src)
    return uploaded


def attachment_ids(html: str) -> set[int]:
    return {int(i) for i in ATTACHMENT_ID_RE.findall(html)}


def find_orphans(client: ZendeskHelpCenter, article_id: int, body: str) -> list[int]:
    """Inline attachment ids on the article that `body` does not reference.

    Non-inline attachments are downloads listed under the article, never
    referenced from the body, so they are not orphans. Never deleted.
    """
    on_article = {
        int(a["id"])
        for a in client.list_attachments(article_id)
        if a.get("inline", True)
    }
    return sorted(on_article - attachment_ids(body))


def check_overwrite_guard(remote_article: dict, article: Article) -> None:
    """Abort when Zendesk changed since this folder was pulled or last published."""
    known = _iso_z(article.last_known_updated_at)
    remote = _iso_z(remote_article.get("updated_at"))
    if known is None:
        raise PublishError(
            "article.yml has an article_id but no last_known_updated_at, so the overwrite "
            f"guard cannot run. Zendesk reports updated_at {remote}. Run "
            f"pull({article.article_id}, <new folder>) and redo the edit there."
        )
    if remote != known:
        raise PublishError(
            "Overwrite guard: the article changed in Zendesk since this folder was "
            f"pulled. article.yml knows {known}; Zendesk reports {remote}. Someone "
            "edited it in Guide. Pull into a new folder and redo the edit there, or "
            "confirm the overwrite by setting last_known_updated_at to the Zendesk value."
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


def verify_readback(translation: dict, title: str, sent_body: str) -> None:
    if translation.get("title") != title:
        raise PublishError(
            f"Read-back title mismatch: sent {title!r}, "
            f"stored {translation.get('title')!r}"
        )
    stored = attachment_ids(translation.get("body") or "")
    missing = sorted(attachment_ids(sent_body) - stored)
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
    orphaned_ids: list[int]
    backup: Path | None


def publish(
    article_dir: Path,
    *,
    live: bool,
    approved_images: frozenset[str] = frozenset(),
    backup_dir: Path | None = None,
    unpublish: bool = False,
    client: ZendeskHelpCenter | None = None,
) -> PublishResult:
    """Create or update the article as a draft; go live only when `live` is True.

    Order: refuse a folder in the checkout; load and check every local image
    (no network yet); resolve visibility; create draft or fetch and guard; back
    up; upload images, rewriting article.html after each; PUT article fields;
    PUT translation; save state; read back; report orphans.

    A live article is never set back to draft unless `unpublish=True`: Zendesk
    has no separate draft of a published article, so `live=False` would take it
    offline for readers.
    """
    backup_dir = backup_dir or article_dir / "backups"
    check_workdir(article_dir)
    check_workdir(backup_dir)
    article = load_article(article_dir)
    if live and article._raw.get("draft") is True:
        raise PublishError(
            f"Article {article.article_id} was a draft when pulled. Publish with "
            "live=False to keep it a draft. To take it live, delete `draft: true` "
            "from article.yml and publish with live=True."
        )
    check_local_images(article, approved_images)
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
        article.last_known_updated_at = _iso_z(created.get("updated_at"))
        save_state(article)  # a later failure must not create a duplicate on re-run
    else:
        remote = client.get_article(article.article_id)
        check_overwrite_guard(remote, article)
        current = client.get_translation(article.article_id)
        if current.get("draft") is False and not live and not unpublish:
            raise PublishError(
                f"Article {article.article_id} is live. Pass live=True to update it in "
                "place, or unpublish=True to take it back to draft, which hides it from "
                "readers until the next live publish."
            )
        backup = backup_translation(current, backup_dir, article)

    uploaded = upload_local_images(client, article, approved_images)

    remote = client.update_article(
        article.article_id,
        {
            "author_id": article.author_id,
            "user_segment_id": segment_id,
            "permission_group_id": group_id,
            "label_names": article.labels,
        },
    )
    article.last_known_updated_at = _iso_z(remote.get("updated_at"))
    save_state(article)
    client.update_translation(
        article.article_id,
        {"title": article.title, "body": article.html, "draft": not live},
    )
    # The translation PUT changes updated_at again. Save before read-back so a
    # read-back failure never leaves the guard blaming someone else's edit.
    article.last_known_updated_at = _iso_z(
        client.get_article(article.article_id)["updated_at"]
    )
    save_state(article)
    verify_readback(
        client.get_translation(article.article_id), article.title, article.html
    )
    return PublishResult(
        article_id=article.article_id,
        html_url=str(remote.get("html_url", "")),
        draft=not live,
        uploaded=uploaded,
        orphaned_ids=find_orphans(client, article.article_id, article.html),
        backup=backup,
    )


def pull(
    article_id: int, workdir: Path, *, client: ZendeskHelpCenter | None = None
) -> Article:
    """Seed a working folder from what Zendesk has now, for an edit.

    Writes article.html (the stored body) and article.yml (fields, visibility
    by name, and the article's updated_at for the overwrite guard). Refuses an
    existing article.html so in-progress edits survive. Every network call runs
    before anything is written.
    """
    check_workdir(workdir)
    if (workdir / "article.html").exists():
        raise PublishError(
            f"{workdir / 'article.html'} already exists. Pull into a new folder so "
            "in-progress edits are not lost."
        )
    client = client or client_from_environment()
    remote = client.get_article(article_id)
    segment_ids = remote.get("user_segment_ids") or []
    if len(segment_ids) > 1:
        raise PublishError(
            f"Article {article_id} is visible to {len(segment_ids)} user segments "
            f"{segment_ids}. The publisher sets one segment and would drop the rest; "
            "change this article's visibility in Guide instead."
        )
    translation = client.get_translation(article_id)
    segment_id = remote.get("user_segment_id")
    if segment_id is None:
        segment = EVERYONE
    else:
        segment = _name_by_id(client.user_segments(), segment_id, "user segment")
    group = _name_by_id(
        client.permission_groups(), remote["permission_group_id"], "permission group"
    )
    meta = {
        "title": translation["title"],
        "section_id": remote["section_id"],
        "author_id": remote["author_id"],
        "labels": list(remote.get("label_names") or []),
        "user_segment": segment,
        "permission_group": group,
        "article_id": article_id,
        "last_known_updated_at": _iso_z(remote["updated_at"]),
        "draft": bool(translation.get("draft")),
    }
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "article.yml").write_text(yaml.safe_dump(meta, sort_keys=False))
    (workdir / "article.html").write_text(translation.get("body") or "")
    return load_article(workdir)


def preview(workdir: Path) -> Path:
    """Wrap article.html in the design system's sample shell. No network.

    Zendesk-hosted images render only if the browser's signed-in Zendesk
    session reaches them from the preview's origin; text and layout always do.
    """
    check_workdir(workdir)
    article = load_article(workdir)
    shell = SHELL_PATH.read_text()
    start = shell.index(BODY_OPEN) + len(BODY_OPEN)
    end = shell.index(SIDE_OPEN)
    page = f"{shell[:start]}\n{article.html}\n    </div>\n    {shell[end:]}"
    heading = f'<h1 class="hc-title">{escape(article.title)}</h1>'
    page = HC_TITLE_RE.sub(lambda _match: heading, page, count=1)
    out = workdir / "preview.html"
    out.write_text(page)
    return out
