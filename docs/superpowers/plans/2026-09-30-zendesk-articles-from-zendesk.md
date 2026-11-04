# Zendesk help articles from Zendesk state Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Zendesk the only copy of a Help Center article: the skill works
in a session-scratchpad folder, `pull` seeds it for edits, and the publisher
refuses any folder inside the checkout.

**Architecture:** `publish_article.py` keeps its folder-based `publish()` but
drops the attachment map. Uploaded images have their `src` rewritten in
`article.html` on disk, so re-runs upload nothing. Orphans come from the
article's attachment list. New `pull()` and `preview()` entry points serve the
edit flow. `SKILL.md` gains the scratchpad folder, the edit flow, and the
auto-mode switch before writes.

**Tech Stack:** Python 3.13, `requests`, `pyyaml`, pytest with the repo's
`FakeSession` stand-in, Zendesk Help Center REST API.

**Spec:**
`docs/superpowers/specs/2026-09-30-zendesk-articles-from-zendesk-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/refactor/claude-zendesk-articles-from-zendesk`.
  Every Bash call uses this absolute path or `git -C <worktree>`; never the main
  checkout path.
- Every publisher entry point (`publish`, `pull`, `preview`) refuses a working
  folder inside the checkout. No article content is written inside the checkout.
- Visibility defaults stay "Signed-in users" and "Agents and admins"; everyone
  only via the literal `everyone`.
- A live article is never set back to draft unless `unpublish=True`.
- Orphaned attachments are reported, never deleted.
- The publisher runs only under pytest (`uv run pytest`), never bare `python`.
- Live Zendesk writes run only after the user has switched out of auto mode and
  approved the exact command.
- `.trunk/trunk.yaml` is protected and unchanged; its design-system ignore
  stays.
- Unit test command, from the worktree:
  `VIRTUAL_ENV= uv run pytest tests/zendesk_help_articles -q 2>&1 | tail -n 15`.
- Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- A pulled body from an older article carries locale-prefixed attachment urls
  (`/hc/en-us/article_attachments/<id>`): those must count as referenced, not as
  orphans or read-back misses. Pinned in Task 2.
- An article visible to more than one user segment (`user_segment_ids` longer
  than 1): `pull` must refuse, because publish sets one segment and would drop
  the rest. Pinned in Task 4.
- A working folder that reaches the checkout through `..`: the refusal must
  compare resolved paths. Pinned in Task 1.
- The draft-then-live second run of a new article: it must upload nothing and
  pass the guard. Pinned in Task 3.
- An attachment list longer than one page: orphans must be computed across every
  page. Pinned in Task 2.

---

### Task 1: Refuse working folders inside the checkout

**Files:**

- Modify: `.claude/skills/zendesk-help-articles/scripts/publish_article.py`
  (module docstring, constants, new `check_workdir`, top of `publish`)
- Test: `tests/zendesk_help_articles/test_article_io.py`,
  `tests/zendesk_help_articles/test_publish.py`

**Interfaces:**

- Produces: `REPO_ROOT: Path` (module global, the checkout root) and
  `check_workdir(path: Path) -> None`, raising `PublishError` whose message
  contains `inside the checkout`. Tests monkeypatch `REPO_ROOT`; the function
  must read the global at call time.

- [ ] **Step 1: Write the failing tests**

Append to `tests/zendesk_help_articles/test_article_io.py`, and add
`import publish_article` plus `check_workdir` to its imports (keep the existing
`trunk-ignore(pyright/reportMissingImports)` comment on the line before the
`from publish_article import` statement, and add the same comment before
`import publish_article`):

```python
def test_repo_root_is_the_checkout():
    root = publish_article.REPO_ROOT
    assert (root / "pyproject.toml").is_file()
    assert (root / ".claude" / "skills" / "zendesk-help-articles").is_dir()


def test_check_workdir_refuses_a_folder_inside_the_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_article, "REPO_ROOT", tmp_path.resolve())
    with pytest.raises(PublishError, match="inside the checkout"):
        check_workdir(tmp_path / "zendesk" / "42")


def test_check_workdir_resolves_dotdot_before_comparing(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    monkeypatch.setattr(publish_article, "REPO_ROOT", repo.resolve())
    with pytest.raises(PublishError, match="inside the checkout"):
        check_workdir(outside / ".." / "repo" / "zendesk")
    check_workdir(outside / "zendesk")
```

Append to `tests/zendesk_help_articles/test_publish.py`, and add
`import publish_article` (with the same trunk-ignore comment) to its imports:

```python
def test_workdir_inside_checkout_refuses_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_article, "REPO_ROOT", tmp_path.resolve())
    (tmp_path / "inside").mkdir()
    d = write_article(tmp_path / "inside")
    client, session = client_for(Server())
    with pytest.raises(PublishError, match="inside the checkout"):
        publish(
            d,
            live=False,
            approved_images=frozenset({"images/a.png"}),
            backup_dir=tmp_path / "bak",
            client=client,
        )
    assert session.calls == []


def test_backup_dir_inside_checkout_refuses_before_network(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(publish_article, "REPO_ROOT", repo.resolve())
    (tmp_path / "work").mkdir()
    d = write_article(tmp_path / "work")
    client, session = client_for(Server())
    with pytest.raises(PublishError, match="inside the checkout"):
        publish(
            d,
            live=False,
            approved_images=frozenset({"images/a.png"}),
            backup_dir=repo / "bak",
            client=client,
        )
    assert session.calls == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from the worktree:
`VIRTUAL_ENV= uv run pytest tests/zendesk_help_articles/test_article_io.py tests/zendesk_help_articles/test_publish.py -q 2>&1 | tail -n 15`

Expected: import error on `check_workdir` (collection fails).

- [ ] **Step 3: Implement**

In `publish_article.py`, replace the module docstring with:

```python
"""Publish a help article working folder to the Zendesk Help Center.

Runs only under pytest: the session fixture in tests/conftest.py loads
ZENDESK_SUBDOMAIN, ZENDESK_EMAIL and ZENDESK_TOKEN from 1Password. The working
folder lives in the session scratchpad; every entry point refuses one inside
the checkout, because Help Center articles are gated and this repo is public.
See .claude/skills/zendesk-help-articles/SKILL.md for the flow and
references/zendesk-api.md for the endpoints.
"""
```

After `TIMEOUT_SECONDS = 60`, add:

```python
# scripts/ -> zendesk-help-articles/ -> skills/ -> .claude/ -> checkout root
REPO_ROOT = Path(__file__).resolve().parents[4]
```

After `_iso_z`, add:

```python
def check_workdir(path: Path) -> None:
    """Refuse a folder inside the checkout. Articles are gated; the repo is public."""
    if path.resolve().is_relative_to(REPO_ROOT):
        raise PublishError(
            f"{path} is inside the checkout ({REPO_ROOT}). Help Center articles are "
            "restricted to signed-in users and this repo is public, so the working "
            "folder must live in the session scratchpad."
        )
```

At the top of `publish()`, before `article = load_article(article_dir)`, add:

```python
    check_workdir(article_dir)
    check_workdir(backup_dir)
```

- [ ] **Step 4: Run the full unit suite**

Run:
`VIRTUAL_ENV= uv run pytest tests/zendesk_help_articles -q 2>&1 | tail -n 15`

Expected: all pass (existing tests use `tmp_path`, which is outside the
checkout).

- [ ] **Step 5: Commit**

```bash
wt=/workspaces/teamster/.claude/worktrees/anthonygwalters/refactor/claude-zendesk-articles-from-zendesk
git -C "$wt" add -u
git -C "$wt" commit -m "feat(zendesk): refuse article working folders inside the checkout" -m "Refs #5628" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Attachment ids in every url form, and orphans from the attachment list

**Files:**

- Modify: `.claude/skills/zendesk-help-articles/scripts/publish_article.py`
  (`ATTACHMENT_ID_RE`, `ZendeskHelpCenter.list_attachments`, new
  `attachment_ids`, new `find_orphans`)
- Create: `tests/zendesk_help_articles/test_orphans.py`

**Interfaces:**

- Produces:
  - `ZendeskHelpCenter.list_attachments(article_id: int) -> list[dict]`,
    following `next_page` and reading the `article_attachments` key strictly (a
    missing key raises `KeyError`, which the live run in Task 6 checks).
  - `attachment_ids(html: str) -> set[int]`, which matches
    `https://<sub>.zendesk.com/hc/article_attachments/<id>/<name>`,
    `/hc/article_attachments/<id>`, and `/hc/en-us/article_attachments/<id>/…`.
  - `find_orphans(client: ZendeskHelpCenter, article_id: int, body: str) -> list[int]`:
    sorted ids on the article that `body` does not reference.

- [ ] **Step 1: Write the failing tests**

Create `tests/zendesk_help_articles/test_orphans.py`:

```python
# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from fakes import FakeSession
from publish_article import ZendeskHelpCenter, attachment_ids, find_orphans

# trunk-ignore-end(pyright/reportMissingImports)

LIST = "/help_center/articles/42/attachments.json"


def client(routes) -> ZendeskHelpCenter:
    return ZendeskHelpCenter("z", "e", "t", session=FakeSession(routes))


def test_attachment_ids_reads_full_short_and_locale_forms():
    html = (
        '<img src="https://z.zendesk.com/hc/article_attachments/101/a.png">'
        '<img src="/hc/article_attachments/102">'
        '<img src="https://z.zendesk.com/hc/en-us/article_attachments/103/b.png">'
        '<img src="images/local.png">'
    )
    assert attachment_ids(html) == {101, 102, 103}


def test_orphans_are_attachments_the_body_does_not_reference():
    c = client(
        {
            ("GET", LIST): (
                200,
                {
                    "article_attachments": [{"id": 101}, {"id": 102}, {"id": 103}],
                    "next_page": None,
                },
            )
        }
    )
    body = (
        '<img src="/hc/article_attachments/101">'
        '<img src="/hc/en-us/article_attachments/103/x.png">'
    )
    assert find_orphans(c, 42, body) == [102]


def test_orphans_follow_next_page():
    c = client(
        {
            ("GET", LIST): (
                200,
                {
                    "article_attachments": [{"id": 1}],
                    "next_page": f"https://z.zendesk.com/api/v2{LIST}?page=2",
                },
            ),
            ("GET", f"{LIST}?page=2"): (
                200,
                {"article_attachments": [{"id": 2}], "next_page": None},
            ),
        }
    )
    assert find_orphans(c, 42, "") == [1, 2]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`VIRTUAL_ENV= uv run pytest tests/zendesk_help_articles/test_orphans.py -q 2>&1 | tail -n 15`

Expected: import error on `attachment_ids`.

- [ ] **Step 3: Implement**

Replace the `ATTACHMENT_ID_RE` line with:

```python
# Full content_url, the shortened relative form, and the locale-prefixed form
# (/hc/en-us/article_attachments/<id>) that older articles may carry.
ATTACHMENT_ID_RE = re.compile(
    r"/hc/(?:[a-z]{2}(?:-[a-z]{2})?/)?article_attachments/(\d+)", re.IGNORECASE
)
```

Add to `ZendeskHelpCenter`, after `update_translation`:

```python
    def list_attachments(self, article_id: int) -> list[dict]:
        """Every attachment on the article, following next_page."""
        path: str | None = f"/help_center/articles/{article_id}/attachments.json"
        items: list[dict] = []
        while path:
            page = self._call("GET", path)
            items.extend(page["article_attachments"])
            next_page = page.get("next_page")
            path = next_page.removeprefix(self.base) if next_page else None
        return items
```

Add after `rewrite_srcs`:

```python
def attachment_ids(html: str) -> set[int]:
    return {int(i) for i in ATTACHMENT_ID_RE.findall(html)}


def find_orphans(client: ZendeskHelpCenter, article_id: int, body: str) -> list[int]:
    """Attachment ids on the article that `body` does not reference. Never deleted."""
    on_article = {int(a["id"]) for a in client.list_attachments(article_id)}
    return sorted(on_article - attachment_ids(body))
```

- [ ] **Step 4: Run the full unit suite**

Run:
`VIRTUAL_ENV= uv run pytest tests/zendesk_help_articles -q 2>&1 | tail -n 15`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
wt=/workspaces/teamster/.claude/worktrees/anthonygwalters/refactor/claude-zendesk-articles-from-zendesk
git -C "$wt" add -u
git -C "$wt" add tests/zendesk_help_articles/test_orphans.py
git -C "$wt" commit -m "feat(zendesk): read orphaned attachments from the article's attachment list" -m "Refs #5628" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Drop the attachment map; rewrite uploaded srcs on disk

This is one atomic swap: removing `Article.attachments` breaks every caller at
once, so the publisher and its four coupled test files change together.

**Files:**

- Replace: `.claude/skills/zendesk-help-articles/scripts/publish_article.py`
  (full content below)
- Replace: `tests/zendesk_help_articles/test_images.py`,
  `tests/zendesk_help_articles/test_guards.py`,
  `tests/zendesk_help_articles/test_publish.py`,
  `tests/zendesk_help_articles/test_review_fixes.py`
- Modify: `tests/zendesk_help_articles/test_article_io.py`,
  `tests/zendesk_help_articles/test_visibility.py`

**Interfaces:**

- Consumes: `check_workdir`, `REPO_ROOT` (Task 1); `attachment_ids`,
  `find_orphans`, `list_attachments` (Task 2).
- Produces:
  - `Article` without `attachments`.
  - `save_html(article: Article) -> None`.
  - `check_local_images(article: Article, approved: frozenset[str]) -> list[str]`.
  - `upload_local_images(client, article, approved) -> list[str]`, returning the
    local srcs uploaded, in order.
  - `rewrite_srcs(html: str, urls: dict[str, str]) -> str`, mapping src to url.
  - `verify_readback(translation: dict, title: str, sent_body: str) -> None`.
  - `publish(article_dir, *, live, approved_images=frozenset(), backup_dir=None, unpublish=False, client=None) -> PublishResult`.
  - `PublishResult(article_id, html_url, draft, uploaded, orphaned_ids, backup)`.
  - `check_overwrite_guard` messages: missing timestamp contains
    `no last_known_updated_at`, the Zendesk timestamp, and `pull`; mismatch
    starts `Overwrite guard:` and names both timestamps.

- [ ] **Step 1: Replace the four coupled test files**

`tests/zendesk_help_articles/test_images.py`:

```python
from pathlib import Path

import pytest
from fakes import FakeSession

# trunk-ignore(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from publish_article import (
    Article,
    PublishError,
    ZendeskHelpCenter,
    check_local_images,
    local_images,
    rewrite_srcs,
    upload_local_images,
)

HTML = (
    '<img src="images/a.png" alt="a">'
    '<img alt="b" src="images/b.png">'
    '<img src="https://cdn.example.org/x.png">'
    '<img src="/hc/article_attachments/5">'
    '<img src="images/a.png">'
)


def test_local_images_skips_absolute_and_dedupes():
    assert local_images(HTML) == ["images/a.png", "images/b.png"]


def test_rewrite_srcs_replaces_only_the_given_srcs():
    out = rewrite_srcs(HTML, {"images/a.png": "https://z/hc/article_attachments/1"})
    assert out.count("https://z/hc/article_attachments/1") == 2
    assert 'src="images/b.png"' in out
    assert 'src="https://cdn.example.org/x.png"' in out


def make(tmp_path: Path, html: str) -> Article:
    (tmp_path / "images").mkdir(exist_ok=True)
    (tmp_path / "article.html").write_text(html)
    return Article(
        dir=tmp_path,
        title="T",
        section_id=1,
        author_id=2,
        user_segment="Signed-in users",
        permission_group="Agents and admins",
        labels=[],
        article_id=42,
        last_known_updated_at=None,
        html=html,
    )


def upload_client(counter: list[int]) -> ZendeskHelpCenter:
    def handler(_kwargs):
        counter.append(1)
        n = 100 + len(counter)
        return 201, {
            "article_attachment": {
                "id": n,
                "content_url": f"https://z/hc/article_attachments/{n}",
            }
        }

    return ZendeskHelpCenter(
        "s",
        "e",
        "t",
        session=FakeSession(
            {("POST", "/help_center/articles/42/attachments.json"): handler}
        ),
    )


def test_missing_file_refuses_before_any_upload(tmp_path):
    a = make(tmp_path, '<img src="images/missing.png">')
    calls: list[int] = []
    with pytest.raises(PublishError, match="images/missing.png"):
        upload_local_images(
            upload_client(calls), a, frozenset({"images/missing.png"})
        )
    assert calls == []


def test_unapproved_image_refuses_before_upload(tmp_path):
    a = make(tmp_path, '<img src="images/a.png">')
    (tmp_path / "images" / "a.png").write_bytes(b"1")
    calls: list[int] = []
    with pytest.raises(PublishError, match="PII gate.*images/a.png"):
        upload_local_images(upload_client(calls), a, frozenset())
    assert calls == []


def test_check_local_images_returns_srcs_in_order(tmp_path):
    a = make(tmp_path, '<img src="images/b.png"><img src="images/a.png">')
    (tmp_path / "images" / "a.png").write_bytes(b"1")
    (tmp_path / "images" / "b.png").write_bytes(b"2")
    approved = frozenset({"images/a.png", "images/b.png"})
    assert check_local_images(a, approved) == ["images/b.png", "images/a.png"]


def test_new_image_uploads_and_rewrites_html_on_disk(tmp_path):
    a = make(tmp_path, '<img src="images/a.png">')
    (tmp_path / "images" / "a.png").write_bytes(b"1")
    calls: list[int] = []
    uploaded = upload_local_images(upload_client(calls), a, frozenset({"images/a.png"}))
    assert uploaded == ["images/a.png"]
    assert a.html == '<img src="https://z/hc/article_attachments/101">'
    assert (tmp_path / "article.html").read_text() == a.html


def test_same_image_twice_uploads_once(tmp_path):
    a = make(tmp_path, '<img src="images/a.png"><img src="images/a.png">')
    (tmp_path / "images" / "a.png").write_bytes(b"1")
    calls: list[int] = []
    upload_local_images(upload_client(calls), a, frozenset({"images/a.png"}))
    assert len(calls) == 1
    assert a.html.count("https://z/hc/article_attachments/101") == 2


def test_zendesk_and_absolute_urls_are_never_uploaded(tmp_path):
    a = make(
        tmp_path,
        '<img src="https://cdn.example.org/x.png">'
        '<img src="/hc/article_attachments/5">'
        '<img src="https://z/hc/en-us/article_attachments/6/x.png">',
    )
    calls: list[int] = []
    assert upload_local_images(upload_client(calls), a, frozenset()) == []
    assert calls == []


def test_upload_needs_an_article_id(tmp_path):
    a = make(tmp_path, "<p>x</p>")
    a.article_id = None
    with pytest.raises(PublishError, match="article_id"):
        upload_local_images(upload_client([]), a, frozenset())
```

`tests/zendesk_help_articles/test_guards.py`:

```python
from pathlib import Path

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from publish_article import (
    Article,
    PublishError,
    backup_translation,
    check_overwrite_guard,
    verify_readback,
)

TITLE = "How to access Tableau"
SENT = '<img src="https://z/hc/article_attachments/101/a.png">'


def article(**overrides) -> Article:
    base = dict(
        dir=Path("."),
        title=TITLE,
        section_id=1,
        author_id=2,
        user_segment="Signed-in users",
        permission_group="Agents and admins",
        labels=[],
        article_id=42,
        last_known_updated_at="2026-09-29T10:00:00Z",
        html="",
    )
    base.update(overrides)
    return Article(**base)


def test_guard_passes_when_timestamps_match():
    check_overwrite_guard({"updated_at": "2026-09-29T10:00:00Z"}, article())


def test_guard_refuses_without_a_timestamp_and_points_at_pull():
    with pytest.raises(
        PublishError, match="no last_known_updated_at.*2026-09-29T11:00:00Z.*pull"
    ):
        check_overwrite_guard(
            {"updated_at": "2026-09-29T11:00:00Z"}, article(last_known_updated_at=None)
        )


def test_guard_normalizes_datetime_against_string():
    from datetime import UTC, datetime

    check_overwrite_guard(
        {"updated_at": "2026-09-29T10:00:00Z"},
        article(last_known_updated_at=datetime(2026, 9, 29, 10, 0, 0, tzinfo=UTC)),
    )


def test_guard_aborts_with_both_timestamps():
    with pytest.raises(
        PublishError, match="Overwrite guard.*2026-09-29T10:00:00Z.*2026-09-29T11:30:00Z"
    ):
        check_overwrite_guard({"updated_at": "2026-09-29T11:30:00Z"}, article())


def test_backup_writes_title_and_body_to_the_given_folder(tmp_path):
    path = backup_translation(
        {"title": "Old", "body": "<p>old</p>"}, tmp_path, article()
    )
    assert path.parent == tmp_path
    assert path.name.startswith("zendesk-article-42-")
    text = path.read_text()
    assert "Old" in text and "<p>old</p>" in text


def test_readback_matches_attachments_by_id_after_url_shortening():
    stored = {"title": TITLE, "body": '<img src="/hc/article_attachments/101">'}
    verify_readback(stored, TITLE, SENT)


def test_readback_fails_on_missing_attachment():
    stored = {"title": TITLE, "body": "<p>no image</p>"}
    with pytest.raises(PublishError, match="101"):
        verify_readback(stored, TITLE, SENT)


def test_readback_allows_extra_stored_attachments():
    stored = {"title": TITLE, "body": '<img src="/hc/article_attachments/101">'}
    verify_readback(stored, TITLE, "<p>no image</p>")


def test_readback_fails_on_title_mismatch():
    stored = {"title": "Other", "body": '<img src="/hc/article_attachments/101">'}
    with pytest.raises(PublishError, match="title"):
        verify_readback(stored, TITLE, SENT)
```

`tests/zendesk_help_articles/test_publish.py` (Task 1's two tests are kept at
the bottom):

```python
from pathlib import Path

# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
import publish_article
import pytest
import yaml
from fakes import FakeSession
from publish_article import PublishError, ZendeskHelpCenter, publish

# trunk-ignore-end(pyright/reportMissingImports)

SEGMENTS = (200, {"user_segments": [{"id": 11, "name": "Signed-in users"}]})
GROUPS = (200, {"permission_groups": [{"id": 21, "name": "Agents and admins"}]})
FIRST_URL = "https://z/hc/article_attachments/101/a.png"


def write_article(
    tmp_path: Path, meta_extra: dict | None = None, html: str | None = None
) -> Path:
    meta = {"title": "T", "section_id": 5, "author_id": 2, "labels": ["tableau"]}
    meta.update(meta_extra or {})
    (tmp_path / "article.yml").write_text(yaml.safe_dump(meta))
    (tmp_path / "article.html").write_text(html or '<p>x</p><img src="images/a.png">')
    (tmp_path / "images").mkdir(exist_ok=True)
    (tmp_path / "images" / "a.png").write_bytes(b"png")
    return tmp_path


class Server:
    """Enough Zendesk state to drive publish() and pull() end to end."""

    def __init__(
        self, existing: dict | None = None, attachment_ids: list[int] | None = None
    ):
        self.article: dict | None = existing
        self.translation: dict = {
            "title": "Old",
            "body": "<p>old</p>",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        self.attachment_ids: list[int] = list(attachment_ids or [])
        self.uploads = 0
        self.writes = 0
        self.article_updates: list[dict] = []
        self.translation_updates: list[dict] = []

    @property
    def updated_at(self) -> str:
        assert self.article is not None
        return self.article["updated_at"]

    def routes(self):
        def create(kw):
            self.article = {
                "id": 42,
                "updated_at": "2026-09-29T10:00:00Z",
                "html_url": "https://z/hc/en-us/articles/42",
                **kw["json"]["article"],
            }
            return 201, {"article": self.article}

        def get_article(_):
            return 200, {"article": self.article}

        def bump():
            self.writes += 1
            stamp = f"2026-09-29T10:{self.writes:02d}:00Z"
            self.article = {**(self.article or {}), "updated_at": stamp}
            return stamp

        def update_article(kw):
            self.article_updates.append(kw["json"]["article"])
            self.article = {**(self.article or {}), **kw["json"]["article"]}
            bump()
            return 200, {"article": self.article}

        def upload(_):
            self.uploads += 1
            n = 100 + self.uploads
            self.attachment_ids.append(n)
            return 201, {
                "article_attachment": {
                    "id": n,
                    "content_url": f"https://z/hc/article_attachments/{n}/a.png",
                }
            }

        def list_attachments(_):
            return 200, {
                "article_attachments": [{"id": i} for i in self.attachment_ids],
                "next_page": None,
            }

        def get_translation(_):
            return 200, {"translation": self.translation}

        def update_translation(kw):
            t = kw["json"]["translation"]
            self.translation_updates.append(t)
            body = t["body"].replace(FIRST_URL, "/hc/article_attachments/101")
            self.translation = {**t, "body": body, "updated_at": bump()}
            return 200, {"translation": self.translation}

        return {
            ("GET", "/help_center/user_segments.json"): SEGMENTS,
            ("GET", "/guide/permission_groups.json"): GROUPS,
            ("POST", "/help_center/sections/5/articles.json"): create,
            ("GET", "/help_center/articles/42.json"): get_article,
            ("PUT", "/help_center/articles/42.json"): update_article,
            ("POST", "/help_center/articles/42/attachments.json"): upload,
            ("GET", "/help_center/articles/42/attachments.json"): list_attachments,
            (
                "GET",
                "/help_center/articles/42/translations/en-us.json",
            ): get_translation,
            (
                "PUT",
                "/help_center/articles/42/translations/en-us.json",
            ): update_translation,
        }


def client_for(server: Server) -> tuple[ZendeskHelpCenter, FakeSession]:
    session = FakeSession(server.routes())
    return ZendeskHelpCenter("z", "e", "t", session=session), session


def existing(updated_at: str = "2026-09-29T10:00:00Z") -> dict:
    return {
        "id": 42,
        "updated_at": updated_at,
        "html_url": "https://z/hc/en-us/articles/42",
    }


def test_first_publish_creates_draft_uploads_and_rewrites_html(tmp_path):
    d = write_article(tmp_path)
    server = Server()
    client, session = client_for(server)
    result = publish(
        d,
        live=False,
        approved_images=frozenset({"images/a.png"}),
        backup_dir=tmp_path / "bak",
        client=client,
    )
    assert result.article_id == 42 and result.draft is True
    assert result.html_url == "https://z/hc/en-us/articles/42"
    assert result.uploaded == ["images/a.png"]
    assert result.orphaned_ids == []
    methods = [m for m, p, _ in session.calls]
    created = session.calls[methods.index("POST")][2]["json"]["article"]
    assert created["draft"] is True and created["user_segment_id"] == 11
    assert created["permission_group_id"] == 21 and created["author_id"] == 2
    assert server.article_updates[-1]["label_names"] == ["tableau"]
    sent = server.translation_updates[-1]
    assert sent["draft"] is True and sent["title"] == "T"
    assert FIRST_URL in sent["body"]
    raw = yaml.safe_load((d / "article.yml").read_text())
    assert raw["article_id"] == 42
    assert raw["last_known_updated_at"] == server.updated_at
    assert "attachments" not in raw
    assert server.writes == 2  # article PUT, then translation PUT
    on_disk = (d / "article.html").read_text()
    assert f'src="{FIRST_URL}"' in on_disk and "images/a.png" not in on_disk


def test_live_publish_sets_draft_false(tmp_path):
    d = write_article(tmp_path)
    client, _ = client_for(Server())
    result = publish(
        d,
        live=True,
        approved_images=frozenset({"images/a.png"}),
        backup_dir=tmp_path / "bak",
        client=client,
    )
    assert result.draft is False


def test_draft_then_live_rerun_uploads_nothing(tmp_path):
    d = write_article(tmp_path)
    server = Server()
    client, _ = client_for(server)
    publish(
        d,
        live=False,
        approved_images=frozenset({"images/a.png"}),
        backup_dir=tmp_path / "bak",
        client=client,
    )
    client2, _ = client_for(server)
    result = publish(d, live=True, backup_dir=tmp_path / "bak", client=client2)
    assert result.uploaded == [] and server.uploads == 1
    assert result.draft is False and result.orphaned_ids == []


def test_existing_article_is_updated_not_recreated_and_backed_up(tmp_path):
    d = write_article(
        tmp_path, {"article_id": 42, "last_known_updated_at": "2026-09-29T10:00:00Z"}
    )
    client, session = client_for(Server(existing=existing()))
    result = publish(
        d, live=False, approved_images=frozenset({"images/a.png"}), client=client
    )
    assert "POST" not in [m for m, p, _ in session.calls if "sections" in p]
    assert result.backup is not None and result.backup.parent == d / "backups"
    assert "<p>old</p>" in result.backup.read_text()


def test_overwrite_guard_stops_before_any_write(tmp_path):
    d = write_article(
        tmp_path, {"article_id": 42, "last_known_updated_at": "2026-09-29T09:00:00Z"}
    )
    client, session = client_for(Server(existing=existing()))
    with pytest.raises(PublishError, match="Overwrite guard"):
        publish(
            d,
            live=False,
            approved_images=frozenset({"images/a.png"}),
            backup_dir=tmp_path / "bak",
            client=client,
        )
    assert [m for m, _, _ in session.calls if m in ("PUT", "POST")] == []


def test_article_id_is_saved_immediately_after_create(tmp_path):
    """A failure after create must not cause a duplicate on re-run."""
    d = write_article(tmp_path)
    server = Server()
    routes = server.routes()
    routes[("POST", "/help_center/articles/42/attachments.json")] = (
        500,
        {"error": "boom"},
    )
    client = ZendeskHelpCenter("z", "e", "t", session=FakeSession(routes))
    with pytest.raises(PublishError, match="500"):
        publish(
            d,
            live=False,
            approved_images=frozenset({"images/a.png"}),
            backup_dir=tmp_path / "bak",
            client=client,
        )
    assert yaml.safe_load((d / "article.yml").read_text())["article_id"] == 42


def test_missing_author_refuses_before_network(tmp_path):
    d = write_article(tmp_path)
    meta = yaml.safe_load((d / "article.yml").read_text())
    del meta["author_id"]
    (d / "article.yml").write_text(yaml.safe_dump(meta))
    client, session = client_for(Server())
    with pytest.raises(PublishError, match="author_id"):
        publish(d, live=False, backup_dir=tmp_path / "bak", client=client)
    assert session.calls == []


def test_orphans_come_from_the_attachment_list(tmp_path):
    d = write_article(
        tmp_path,
        {"article_id": 42, "last_known_updated_at": "2026-09-29T10:00:00Z"},
        html='<p>x</p><img src="/hc/article_attachments/7">',
    )
    server = Server(existing=existing(), attachment_ids=[7, 8])
    client, _ = client_for(server)
    result = publish(d, live=False, backup_dir=tmp_path / "bak", client=client)
    assert result.uploaded == [] and server.uploads == 0
    assert result.orphaned_ids == [8]


def test_workdir_inside_checkout_refuses_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_article, "REPO_ROOT", tmp_path.resolve())
    (tmp_path / "inside").mkdir()
    d = write_article(tmp_path / "inside")
    client, session = client_for(Server())
    with pytest.raises(PublishError, match="inside the checkout"):
        publish(
            d,
            live=False,
            approved_images=frozenset({"images/a.png"}),
            backup_dir=tmp_path / "bak",
            client=client,
        )
    assert session.calls == []


def test_backup_dir_inside_checkout_refuses_before_network(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(publish_article, "REPO_ROOT", repo.resolve())
    (tmp_path / "work").mkdir()
    d = write_article(tmp_path / "work")
    client, session = client_for(Server())
    with pytest.raises(PublishError, match="inside the checkout"):
        publish(
            d,
            live=False,
            approved_images=frozenset({"images/a.png"}),
            backup_dir=repo / "bak",
            client=client,
        )
    assert session.calls == []
```

`tests/zendesk_help_articles/test_review_fixes.py`:

```python
"""Tests from the whole-branch review: local checks before network, state saved
as soon as Zendesk changes, and input hardening."""

from pathlib import Path

import pytest
import yaml

# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from fakes import FakeSession
from publish_article import (
    TIMEOUT_SECONDS,
    PublishError,
    ZendeskHelpCenter,
    load_article,
    local_images,
    publish,
    rewrite_srcs,
)
from test_publish import FIRST_URL, Server, client_for, existing, write_article

# trunk-ignore-end(pyright/reportMissingImports)


def run(d: Path, client, **kw):
    kw.setdefault("live", False)
    kw.setdefault("approved_images", frozenset({"images/a.png"}))
    kw.setdefault("backup_dir", d / "bak")
    return publish(d, client=client, **kw)


def test_missing_image_refuses_before_any_network(tmp_path):
    d = write_article(tmp_path, html='<img src="images/missing.png">')
    client, session = client_for(Server())
    with pytest.raises(PublishError, match="images/missing.png"):
        run(d, client)
    assert session.calls == []
    assert yaml.safe_load((d / "article.yml").read_text()).get("article_id") is None


def test_unapproved_image_refuses_before_any_network(tmp_path):
    d = write_article(tmp_path)
    client, session = client_for(Server())
    with pytest.raises(PublishError, match="PII gate"):
        run(d, client, approved_images=frozenset())
    assert session.calls == []


def test_state_saved_even_when_readback_fails(tmp_path):
    d = write_article(tmp_path)
    server = Server()
    routes = server.routes()
    real_update = routes[("PUT", "/help_center/articles/42/translations/en-us.json")]

    def drop_image(kw):
        status, _payload = real_update(kw)
        server.translation["body"] = "<p>sanitizer ate the image</p>"
        return status, {"translation": server.translation}

    routes[("PUT", "/help_center/articles/42/translations/en-us.json")] = drop_image
    client = ZendeskHelpCenter("z", "e", "t", session=FakeSession(routes))
    with pytest.raises(PublishError, match="Read-back"):
        run(d, client)
    raw = yaml.safe_load((d / "article.yml").read_text())
    assert raw["last_known_updated_at"] == server.updated_at
    assert FIRST_URL in (d / "article.html").read_text()


def test_create_saves_timestamp_so_rerun_passes_guard(tmp_path):
    d = write_article(tmp_path)
    server = Server()
    routes = server.routes()
    routes[("POST", "/help_center/articles/42/attachments.json")] = (
        500,
        {"error": "boom"},
    )
    client = ZendeskHelpCenter("z", "e", "t", session=FakeSession(routes))
    with pytest.raises(PublishError, match="500"):
        run(d, client)
    raw = yaml.safe_load((d / "article.yml").read_text())
    assert raw["article_id"] == 42
    assert raw["last_known_updated_at"] == server.updated_at
    client2, session2 = client_for(server)
    run(d, client2)
    assert [p for m, p, _ in session2.calls if m == "POST" and "sections" in p] == []


def test_unquoted_timestamp_in_yaml_still_matches_guard(tmp_path):
    d = write_article(tmp_path, {"article_id": 42})
    yml = d / "article.yml"
    yml.write_text(yml.read_text() + "last_known_updated_at: 2026-09-29T10:00:00Z\n")
    client, _ = client_for(Server(existing=existing()))
    run(d, client)


def test_hand_entered_article_id_without_timestamp_refuses(tmp_path):
    d = write_article(tmp_path, {"article_id": 42})
    client, session = client_for(Server(existing=existing()))
    with pytest.raises(PublishError, match="2026-09-29T10:00:00Z.*pull"):
        run(d, client)
    assert [m for m, _, _ in session.calls if m in ("PUT", "POST")] == []


def test_live_article_is_not_demoted_without_unpublish(tmp_path):
    d = write_article(
        tmp_path, {"article_id": 42, "last_known_updated_at": "2026-09-29T10:00:00Z"}
    )
    server = Server(existing=existing())
    server.translation["draft"] = False
    client, session = client_for(server)
    with pytest.raises(PublishError, match="live"):
        run(d, client)
    assert [m for m, _, _ in session.calls if m in ("PUT", "POST")] == []
    client2, _ = client_for(server)
    result = run(d, client2, unpublish=True)
    assert result.draft is True
    assert server.translation_updates[-1]["draft"] is True


def test_every_request_carries_a_timeout(tmp_path):
    d = write_article(tmp_path)
    client, session = client_for(Server())
    run(d, client)
    assert session.calls and all(
        kw.get("timeout") == TIMEOUT_SECONDS for _, _, kw in session.calls
    )


def test_single_quoted_src_is_found_and_data_src_is_not():
    html = "<img src='images/a.png' data-src=\"images/b.png\"><img data-src='images/c.png'>"
    assert local_images(html) == ["images/a.png"]
    out = rewrite_srcs(html, {"images/a.png": "https://z/1"})
    assert "src='https://z/1'" in out and 'data-src="images/b.png"' in out


def test_labels_string_becomes_single_label(tmp_path):
    d = write_article(tmp_path, {"labels": "tableau"})
    assert load_article(d).labels == ["tableau"]


def test_src_outside_article_folder_refuses(tmp_path):
    (tmp_path / "outside.png").write_bytes(b"x")
    (tmp_path / "art").mkdir()
    d = write_article(tmp_path / "art", html='<img src="../outside.png">')
    client, session = client_for(Server())
    with pytest.raises(PublishError, match="outside"):
        run(d, client, approved_images=frozenset({"../outside.png"}))
    assert session.calls == []


def test_partial_upload_failure_keeps_uploaded_images_on_disk(tmp_path):
    d = write_article(tmp_path, html='<img src="images/a.png"><img src="images/b.png">')
    (d / "images" / "b.png").write_bytes(b"png2")
    server = Server()
    routes = server.routes()
    real_upload = routes[("POST", "/help_center/articles/42/attachments.json")]

    def second_fails(kw):
        if server.uploads == 1:
            server.uploads += 1  # count the attempt so later ids stay unique
            return 500, {"error": "boom"}
        return real_upload(kw)

    routes[("POST", "/help_center/articles/42/attachments.json")] = second_fails
    client = ZendeskHelpCenter("z", "e", "t", session=FakeSession(routes))
    both = frozenset({"images/a.png", "images/b.png"})
    with pytest.raises(PublishError, match="500"):
        run(d, client, approved_images=both)
    on_disk = (d / "article.html").read_text()
    assert FIRST_URL in on_disk and 'src="images/b.png"' in on_disk
    client2, _ = client_for(server)
    result = run(d, client2, approved_images=frozenset({"images/b.png"}))
    assert result.uploaded == ["images/b.png"]
```

- [ ] **Step 2: Update the two lightly coupled test files**

In `tests/zendesk_help_articles/test_visibility.py`, delete the line
`        attachments={},` inside the `Article(...)` call.

In `tests/zendesk_help_articles/test_article_io.py`:

- In `test_load_applies_visibility_defaults`, delete
  `    assert a.attachments == {}`.
- Replace `test_save_state_round_trips_and_keeps_user_fields` with:

```python
def test_save_state_round_trips_and_keeps_user_fields(tmp_path):
    d = write_article(
        tmp_path,
        {"title": "T", "section_id": 1, "author_id": 2, "labels": ["x"]},
    )
    a = load_article(d)
    a.article_id = 99
    a.last_known_updated_at = "2026-09-29T00:00:00Z"
    save_state(a)
    raw = yaml.safe_load((d / "article.yml").read_text())
    assert raw["labels"] == ["x"]
    assert raw["article_id"] == 99
    assert raw["last_known_updated_at"] == "2026-09-29T00:00:00Z"
    assert "attachments" not in raw
    again = load_article(d)
    assert again.article_id == 99


def test_save_html_writes_the_body(tmp_path):
    d = write_article(tmp_path, {"title": "T", "section_id": 1, "author_id": 2})
    a = load_article(d)
    a.html = "<p>changed</p>"
    save_html(a)
    assert (d / "article.html").read_text() == "<p>changed</p>"
```

and add `save_html` to its `from publish_article import (...)` list.

- [ ] **Step 3: Run the tests to verify they fail**

Run:
`VIRTUAL_ENV= uv run pytest tests/zendesk_help_articles -q 2>&1 | tail -n 15`

Expected: collection errors importing `check_local_images`,
`upload_local_images` and `save_html`.

- [ ] **Step 4: Replace `publish_article.py`**

Full content of
`.claude/skills/zendesk-help-articles/scripts/publish_article.py`:

```python
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
    """Refuse a folder inside the checkout. Articles are gated; the repo is public."""
    if path.resolve().is_relative_to(REPO_ROOT):
        raise PublishError(
            f"{path} is inside the checkout ({REPO_ROOT}). Help Center articles are "
            "restricted to signed-in users and this repo is public, so the working "
            "folder must live in the session scratchpad."
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

    def list_attachments(self, article_id: int) -> list[dict]:
        """Every attachment on the article, following next_page."""
        path: str | None = f"/help_center/articles/{article_id}/attachments.json"
        items: list[dict] = []
        while path:
            page = self._call("GET", path)
            items.extend(page["article_attachments"])
            next_page = page.get("next_page")
            path = next_page.removeprefix(self.base) if next_page else None
        return items

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
    """Attachment ids on the article that `body` does not reference. Never deleted."""
    on_article = {int(a["id"]) for a in client.list_attachments(article_id)}
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
```

- [ ] **Step 5: Run the full unit suite**

Run:
`VIRTUAL_ENV= uv run pytest tests/zendesk_help_articles -q 2>&1 | tail -n 15`

Expected: all pass. Then confirm nothing still names the removed pieces:
`rg -n "sha256|\.attachments\b|reused|sync_attachments" .claude/skills/zendesk-help-articles/scripts tests/zendesk_help_articles`
Expected: no output.

- [ ] **Step 6: Commit**

```bash
wt=/workspaces/teamster/.claude/worktrees/anthonygwalters/refactor/claude-zendesk-articles-from-zendesk
git -C "$wt" add -u
git -C "$wt" commit -m "refactor(zendesk): rewrite uploaded image srcs in place instead of tracking an attachment map" -m "Refs #5628" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `pull()` and `preview()`

**Files:**

- Modify: `.claude/skills/zendesk-help-articles/scripts/publish_article.py`
  (imports, constants, new `_name_by_id`, `pull`, `preview`)
- Create: `tests/zendesk_help_articles/test_pull.py`

**Interfaces:**

- Consumes: `check_workdir`, `load_article`, `client_from_environment`,
  `EVERYONE`, `_iso_z` (earlier tasks); `Server`, `client_for`, `existing` from
  `test_publish.py` (Task 3).
- Produces:
  - `pull(article_id: int, workdir: Path, *, client: ZendeskHelpCenter | None = None) -> Article`
  - `preview(workdir: Path) -> Path` (returns `workdir / "preview.html"`)

- [ ] **Step 1: Write the failing tests**

Create `tests/zendesk_help_articles/test_pull.py`:

```python
# trunk-ignore-begin(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
import publish_article
import pytest
import yaml
from fakes import FakeSession
from publish_article import PublishError, ZendeskHelpCenter, preview, publish, pull
from test_publish import Server, client_for, existing

# trunk-ignore-end(pyright/reportMissingImports)

BODY = '<p>Body</p><img src="/hc/en-us/article_attachments/7/a.png">'


def remote_article(**overrides) -> dict:
    base = {
        "id": 42,
        "section_id": 5,
        "author_id": 2,
        "label_names": ["powerschool"],
        "user_segment_id": 11,
        "user_segment_ids": [11],
        "permission_group_id": 22,
        "updated_at": "2026-09-29T22:15:49Z",
    }
    base.update(overrides)
    return base


def pull_client(article: dict) -> tuple[ZendeskHelpCenter, FakeSession]:
    session = FakeSession(
        {
            ("GET", "/help_center/articles/42.json"): (200, {"article": article}),
            ("GET", "/help_center/articles/42/translations/en-us.json"): (
                200,
                {"translation": {"title": "How to add students", "body": BODY}},
            ),
            ("GET", "/help_center/user_segments.json"): (
                200,
                {"user_segments": [{"id": 11, "name": "Signed-in users"}]},
            ),
            ("GET", "/guide/permission_groups.json"): (
                200,
                {
                    "permission_groups": [
                        {"id": 21, "name": "Agents and admins"},
                        {"id": 22, "name": "Admins"},
                    ]
                },
            ),
        }
    )
    return ZendeskHelpCenter("z", "e", "t", session=session), session


def test_pull_writes_body_and_fields(tmp_path):
    client, _ = pull_client(remote_article())
    a = pull(42, tmp_path / "42", client=client)
    raw = yaml.safe_load((tmp_path / "42" / "article.yml").read_text())
    assert raw == {
        "title": "How to add students",
        "section_id": 5,
        "author_id": 2,
        "labels": ["powerschool"],
        "user_segment": "Signed-in users",
        "permission_group": "Admins",
        "article_id": 42,
        "last_known_updated_at": "2026-09-29T22:15:49Z",
    }
    assert (tmp_path / "42" / "article.html").read_text() == BODY
    assert a.article_id == 42 and a.html == BODY


def test_pull_maps_a_null_segment_to_everyone(tmp_path):
    client, _ = pull_client(remote_article(user_segment_id=None, user_segment_ids=[]))
    pull(42, tmp_path / "42", client=client)
    raw = yaml.safe_load((tmp_path / "42" / "article.yml").read_text())
    assert raw["user_segment"] == "everyone"


def test_pull_refuses_an_existing_article_html(tmp_path):
    (tmp_path / "article.html").write_text("<p>in progress</p>")
    client, session = pull_client(remote_article())
    with pytest.raises(PublishError, match="already exists"):
        pull(42, tmp_path, client=client)
    assert session.calls == []
    assert (tmp_path / "article.html").read_text() == "<p>in progress</p>"


def test_pull_refuses_a_workdir_inside_the_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_article, "REPO_ROOT", tmp_path.resolve())
    client, session = pull_client(remote_article())
    with pytest.raises(PublishError, match="inside the checkout"):
        pull(42, tmp_path / "42", client=client)
    assert session.calls == []


def test_pull_refuses_more_than_one_user_segment(tmp_path):
    client, _ = pull_client(remote_article(user_segment_ids=[11, 12]))
    with pytest.raises(PublishError, match="2 user segments"):
        pull(42, tmp_path / "42", client=client)
    assert not (tmp_path / "42").exists()


def pulled_server() -> Server:
    server = Server(
        existing={
            **existing(),
            **remote_article(permission_group_id=21, updated_at="2026-09-29T10:00:00Z"),
        },
        attachment_ids=[7],
    )
    server.translation = {"title": "How to add students", "body": BODY}
    return server


def test_pulled_folder_publishes_unchanged_with_zero_uploads(tmp_path):
    server = pulled_server()
    client, _ = client_for(server)
    pull(42, tmp_path / "42", client=client)
    client2, _ = client_for(server)
    result = publish(tmp_path / "42", live=True, client=client2)
    assert result.uploaded == [] and server.uploads == 0
    assert result.orphaned_ids == []


def test_guide_edit_after_pull_is_refused(tmp_path):
    server = pulled_server()
    client, _ = client_for(server)
    pull(42, tmp_path / "42", client=client)
    assert server.article is not None
    server.article["updated_at"] = "2026-09-29T11:00:00Z"  # someone edits in Guide
    client2, session = client_for(server)
    with pytest.raises(PublishError, match="Overwrite guard"):
        publish(tmp_path / "42", live=True, client=client2)
    assert [m for m, _, _ in session.calls if m in ("PUT", "POST")] == []


def test_preview_wraps_the_body_in_the_shell(tmp_path):
    client, _ = pull_client(remote_article())
    pull(42, tmp_path / "42", client=client)
    out = preview(tmp_path / "42")
    page = out.read_text()
    assert out == tmp_path / "42" / "preview.html"
    assert BODY in page and 'class="hc-side"' in page
    assert '<h1 class="hc-title">How to add students</h1>' in page
    assert "walks you through submitting" not in page


def test_preview_escapes_the_title(tmp_path):
    (tmp_path / "article.yml").write_text(
        yaml.safe_dump({"title": "A & B <c>", "section_id": 1, "author_id": 2})
    )
    (tmp_path / "article.html").write_text("<p>x</p>")
    page = preview(tmp_path).read_text()
    assert '<h1 class="hc-title">A &amp; B &lt;c&gt;</h1>' in page
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`VIRTUAL_ENV= uv run pytest tests/zendesk_help_articles/test_pull.py -q 2>&1 | tail -n 15`

Expected: import error on `preview`.

- [ ] **Step 3: Implement**

Add `from html import escape` to the imports (after `from datetime import ...`
keep stdlib imports alphabetical: `from html import escape` goes after
`from datetime import UTC, datetime`).

After `REPO_ROOT`, add:

```python
SHELL_PATH = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "design-system"
    / "sample-article.html"
)
BODY_OPEN = '<div class="article-body">'
SIDE_OPEN = '<div class="hc-side">'
HC_TITLE_RE = re.compile(r'<h1 class="hc-title">.*?</h1>', re.DOTALL)
```

After `_id_by_name`, add:

```python
def _name_by_id(items: list[dict], item_id: int, kind: str) -> str:
    for item in items:
        if int(item["id"]) == int(item_id):
            return str(item["name"])
    raise PublishError(f"No {kind} with id {item_id} in Zendesk")
```

After `publish`, add:

```python
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
```

- [ ] **Step 4: Run the full unit suite**

Run:
`VIRTUAL_ENV= uv run pytest tests/zendesk_help_articles -q 2>&1 | tail -n 15`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
wt=/workspaces/teamster/.claude/worktrees/anthonygwalters/refactor/claude-zendesk-articles-from-zendesk
git -C "$wt" add -u
git -C "$wt" add tests/zendesk_help_articles/test_pull.py
git -C "$wt" commit -m "feat(zendesk): add pull and preview for editing articles from Zendesk" -m "Refs #5628" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Skill, API reference, and repo config

**Files:**

- Replace: `.claude/skills/zendesk-help-articles/SKILL.md`
- Modify: `.claude/skills/zendesk-help-articles/references/zendesk-api.md`
- Modify: `.gitignore` (delete line `docs/help-center/*/images/`)
- Modify: `mkdocs.yml` (delete line `  help-center/` under `exclude_docs`)

**Interfaces:**

- Consumes: the entry points and `PublishResult` fields from Tasks 3 and 4.

- [ ] **Step 1: Replace `SKILL.md`**

Open it with the Read tool first (it loads the skill-editing rule). Full
content:

````markdown
---
name: zendesk-help-articles
description:
  Use when writing, editing, or publishing a KTAF Zendesk Help Center article
  ("write a help article for X", "draft the Zendesk article", "update the help
  article on Y", a re-publish after an edit), when a published article shows the
  wrong author, its body did not change after an update, or its images do not
  render, or when asked whether the Dagster ZendeskResource or a Zendesk MCP can
  publish articles.
---

# Zendesk help articles

Zendesk holds the only copy of an article. Work happens in a folder in the
session scratchpad: `pull` fills it for an edit, you compose it for a new
article, and `publish` writes it back.

## Non-negotiables

- Read `references/design-system/README.md` before writing any article HTML.
  Inline styles only; `margin` only on `<table>`; `<div>` not `<p>` inside a
  `<td>`; empty elements are deleted; the sanitizer runs at render, so the
  stored body proves storage, not appearance.
- Read `references/zendesk-api.md` before any publish.
- The working folder is `<session scratchpad>/zendesk/<article_id or slug>/`.
  `publish`, `pull` and `preview` refuse a folder inside the checkout: articles
  are restricted to signed-in users and this repo is public.
- Every publisher call runs under pytest, through a throwaway
  `tests/test_zz_zendesk_<id or slug>.py` that holds only the folder path and
  flags, deleted afterward. A bare `uv run python` has no credentials. Neither
  the Dagster `ZendeskResource` (scope `read users:write`) nor any connected MCP
  can write to the Help Center.
- Before the first Zendesk write in a session (publish, unpublish, archive,
  permission change), if auto mode is on: stop, show the exact command, and ask
  the user to switch to manual mode with Shift+Tab. Run it only after they
  confirm, then tell them they can switch back. Auto mode's classifier can
  refuse a write it allowed minutes earlier; reads (`pull`, `preview`, searches,
  dry runs) stay in auto.
- Draft first for a new article. Going live is a second call with `live=True`,
  after the user has seen the draft. An article that is already live is updated
  in place with `live=True`; the publisher refuses `live=False` on it unless
  `unpublish=True`, because Zendesk has no draft of a live article and the page
  would vanish for readers.
- No image uploads without the PII gate below.

## Working folder

```text
<session scratchpad>/zendesk/<article_id or slug>/
  article.html   body only, no <html> shell
  article.yml    title, section_id, author_id, labels; optional user_segment,
                 permission_group; publisher-owned article_id,
                 last_known_updated_at
  images/        new screenshots, referenced by relative path
  preview.html   written by preview()
  backups/       the stored body before each overwrite
```

`author_id` is required. Visibility defaults to the "Signed-in users" segment
and the "Agents and admins" permission group; override by name in the file.
`user_segment: everyone` is the only way to publish to everyone.

`last_known_updated_at` is Zendesk's `updated_at` when the folder was pulled,
refreshed after each publish. If Zendesk's value differs at publish time,
someone edited in Guide and the publisher refuses. After each upload the
publisher rewrites that image's `src` in `article.html` to its Zendesk url, so
an image is never uploaded twice. The publisher rewrites `article.yml` on every
run, so comments in it do not survive.

The scratchpad ends with the session. To edit an article again later, pull it
again.

## Runner

```python
import sys
from pathlib import Path

sys.path.insert(0, ".claude/skills/zendesk-help-articles/scripts")
from publish_article import preview, publish, pull  # noqa: E402

WORKDIR = Path("<session scratchpad>/zendesk/<article_id or slug>")


def test_run():
    print(publish(WORKDIR, live=False, approved_images=frozenset({"images/01-home.png"})))
```

Swap the call in `test_run` for the step at hand, then
`cd <checkout> && uv run pytest tests/test_zz_zendesk_<id or slug>.py -s`.

## New article

1. Read the design-system README. Compose `article.html` from
   `references/design-system/snippets/` in the README's article order: summary
   panel, in-this-article, `<h2>` sections with numbered steps and callouts,
   screenshots, related articles. No `<h1>`.
2. Reference each screenshot as `<img src="images/<name>.png">` inside the
   screenshot snippet.
3. Write `article.yml` with `title` (a plain sentence) and `labels`; ask the
   user for `section_id` and `author_id`.
4. PII gate for each image.
5. Auto-mode check, then `publish(WORKDIR, live=False, approved_images=...)`.
6. Show the draft url and the report. Ask the user to open the draft signed in.
   This is the preview: the draft shows what the sanitizer does. Stop until they
   approve.
7. `publish(WORKDIR, live=True)`. Nothing is uploaded this time; the images are
   Zendesk urls now.
8. Ask the user to confirm the live page renders. Delete the test file.

## Edit an existing article

1. `pull(<article_id>, WORKDIR)`.
2. Edit `article.html`. For a new or replaced screenshot, save it under
   `images/` and point the `src` at it.
3. `preview(WORKDIR)`, then serve the folder with
   `uv run python -m http.server 8765 --directory <WORKDIR>` as a background
   Bash job. VS Code forwards the port; ask the user to open `/preview.html` on
   it in a browser or VS Code's Simple Browser. Images already on Zendesk render
   only if the browser's Zendesk session reaches them; text and layout always
   render. Stop until they approve, then stop the server.
4. PII gate for any new image.
5. Auto-mode check, then `publish(WORKDIR, live=True, approved_images=...)`.
6. Show the report. Ask the user to open the page signed in and confirm it
   renders. Delete the test file.

## PII gate

For every local image the body references: open it with the Read tool, state in
plain words what is visible (school, grade band, any names, any count small
enough to identify a student), and wait for the user's yes. Collect the approved
relative paths for `approved_images`; the publisher refuses any local image not
in it.

## Report

`publish` returns `uploaded` (local images uploaded this run), `orphaned_ids`
(attachments on the article the body no longer references; reported, never
deleted), `backup`, `html_url` and `draft`. A `PublishError` message is written
for the user. Show it verbatim. The overwrite guard names both timestamps and
how to proceed.
````

- [ ] **Step 2: Update `references/zendesk-api.md`**

Open it with the Read tool first. Make these edits:

In the _Calls in publish order_ table, insert as the first row:

```markdown
| Pull | `GET /help_center/articles/{id}.json`, then the `en-us` translation |
fields, `user_segment_ids`, `updated_at`; stored `title` and `body` |
```

Change the Fetch row's note from `` `updated_at` drives the overwrite guard ``
to `` `updated_at` must equal the value `pull` or the last publish recorded ``.

Append after the Read back row:

```markdown
| Orphans | `GET /help_center/articles/{id}/attachments.json` |
`article_attachments[].id`; follow `next_page` |
```

(Let prettier re-align the table in Step 4.)

Replace the last _Traps_ bullet with:

```markdown
- The translation `PUT` changes the article's `updated_at` after the article
  `PUT` returned. Fetch the article again before saving `last_known_updated_at`
  to the working folder's `article.yml`.
- Attachment urls come in three forms: the full `content_url`, the shortened
  `/hc/article_attachments/<id>`, and on older articles possibly the
  locale-prefixed `/hc/en-us/article_attachments/<id>`. Match on the id.
```

In _Verified live_, replace
`A re-run with no changes uploaded nothing and reused the recorded attachment.`
with
`A re-run with no changes uploaded nothing: the body already pointed at the attachment's url.`

- [ ] **Step 3: Remove the repo-folder config**

In `.gitignore`, delete the line `docs/help-center/*/images/`. In `mkdocs.yml`,
delete the line `  help-center/` under `exclude_docs: |`.

Then confirm nothing still points at the old folder:
`rg -n --hidden --glob '!.git' --glob '!docs/superpowers/**' "docs/help-center|help-center/" .`
Expected: no output (the earlier spec and plan under `docs/superpowers/` are
left as written).

- [ ] **Step 4: Lint the edited markdown and YAML**

From the worktree:
`/workspaces/teamster/.trunk/tools/trunk fmt .claude/skills/zendesk-help-articles/SKILL.md .claude/skills/zendesk-help-articles/references/zendesk-api.md mkdocs.yml </dev/null 2>&1 | tail -n 5`
then
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/zendesk-help-articles/SKILL.md .claude/skills/zendesk-help-articles/references/zendesk-api.md mkdocs.yml </dev/null 2>&1 | tail -n 15`

Expected: `No issues`.

- [ ] **Step 5: Commit**

```bash
wt=/workspaces/teamster/.claude/worktrees/anthonygwalters/refactor/claude-zendesk-articles-from-zendesk
git -C "$wt" add -u
git -C "$wt" commit -m "docs(zendesk): work from Zendesk state in the session scratchpad, never the repo" -m "Refs #5628" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Live acceptance against Zendesk

Writes to production Zendesk. Do not dispatch this task to a subagent; the
session that talks to the user runs it.

**Files:**

- Create then delete: `tests/test_zz_zendesk_acceptance.py`
- Modify: `.claude/skills/zendesk-help-articles/references/zendesk-api.md`
  (record results)

**Interfaces:**

- Consumes: `publish`, `pull`, `find_orphans`, `attachment_ids`,
  `client_from_environment`, `PublishError` (Tasks 2 to 4).

- [ ] **Step 1: Read-only check against a real article**

Write `tests/test_zz_zendesk_acceptance.py`, with `<scratchpad>` replaced by the
session scratchpad's absolute path:

```python
import sys
from pathlib import Path

sys.path.insert(0, ".claude/skills/zendesk-help-articles/scripts")
from publish_article import (  # noqa: E402
    attachment_ids,
    client_from_environment,
    find_orphans,
    local_images,
    pull,
)

SCRATCH = Path("<scratchpad>/zendesk-acceptance")


def test_read_only():
    folder = SCRATCH / "real-360035629314"
    article = pull(360035629314, folder)
    ids = attachment_ids(article.html)
    print("img tags:", article.html.count("<img"), "attachment ids:", len(ids))
    print("local srcs:", local_images(article.html))
    print("orphans:", find_orphans(client_from_environment(), 360035629314, article.html))
```

Run:
`cd <worktree> && uv run pytest tests/test_zz_zendesk_acceptance.py -s 2>&1 | tail -n 15`

Expected: `img tags` equals `attachment ids` (10 each per PR #5627's read-back),
`local srcs: []`, and an orphan list that prints without a `KeyError`
(confirming the `article_attachments` key). If `img tags` exceeds
`attachment ids`, show the unmatched `src` forms to the user before going on:
the regex misses a url form.

- [ ] **Step 2: Ask the user for the throwaway article's section and author**

Ask for a `section_id` to hold a throwaway draft and the `author_id` to use.
Wait for both.

- [ ] **Step 3: Write the write-path acceptance test**

Replace the file's content with:

```python
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, ".claude/skills/zendesk-help-articles/scripts")
from publish_article import (  # noqa: E402
    PublishError,
    client_from_environment,
    publish,
    pull,
)

SCRATCH = Path("<scratchpad>/zendesk-acceptance")
SECTION_ID = 0  # the value the user gave in Step 2
AUTHOR_ID = 0  # the value the user gave in Step 2


def tiny_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\xff\xff")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


def git_status() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
    ).stdout


def test_acceptance():
    before = git_status()
    new = SCRATCH / "new"
    (new / "images").mkdir(parents=True)
    (new / "images" / "dot.png").write_bytes(tiny_png())
    (new / "article.html").write_text(
        '<p>Throwaway acceptance article for issue 5628.</p>'
        '<img src="images/dot.png" alt="dot">'
    )
    (new / "article.yml").write_text(
        yaml.safe_dump(
            {
                "title": "Throwaway acceptance article",
                "section_id": SECTION_ID,
                "author_id": AUTHOR_ID,
                "labels": ["zz-acceptance"],
            }
        )
    )
    first = publish(new, live=False, approved_images=frozenset({"images/dot.png"}))
    print("1 created draft:", first)
    client = client_from_environment()
    try:
        assert first.uploaded == ["images/dot.png"]

        rerun = publish(new, live=False)
        print("2 same-folder rerun:", rerun)
        assert rerun.uploaded == []

        edit = SCRATCH / "edit"
        pull(first.article_id, edit)
        unchanged = publish(edit, live=False)
        print("3 pulled, published unchanged:", unchanged)
        assert unchanged.uploaded == [] and unchanged.orphaned_ids == []

        guarded = SCRATCH / "guarded"
        pull(first.article_id, guarded)
        body = client.get_translation(first.article_id)["body"]
        client.update_translation(
            first.article_id, {"body": body + "<p>Guide edit</p>"}
        )
        with pytest.raises(PublishError, match="Overwrite guard") as refused:
            publish(guarded, live=False)
        print("4 guard refused:", refused.value)
    finally:
        response = client.session.request(
            "DELETE",
            f"{client.base}/help_center/articles/{first.article_id}.json",
            timeout=60,
        )
        print("5 archived:", response.status_code)
        assert response.status_code == 204
    assert git_status() == before
```

- [ ] **Step 4: Run it in manual mode with the user's approval**

Tell the user, in plain text, that the next command creates a throwaway draft
article with a 1×1 white pixel image (nothing identifiable; this is its PII
gate), republishes it twice, simulates a Guide edit, and archives the article at
the end. If auto mode is on, ask them to switch to manual with Shift+Tab. Show
the exact command and wait for their go-ahead:

`cd /workspaces/teamster/.claude/worktrees/anthonygwalters/refactor/claude-zendesk-articles-from-zendesk && uv run pytest tests/test_zz_zendesk_acceptance.py -s 2>&1 | tail -n 30`

Expected: lines 1 to 5 print, `5 archived: 204`, and the test passes. Then tell
the user they can switch back to auto.

If it fails before line 5, the `finally` block still archives the article;
confirm `5 archived: 204` printed. If it did not, give the user the article id
and ask them to archive it in Guide.

- [ ] **Step 5: Delete the throwaway test and confirm a clean checkout**

```bash
wt=/workspaces/teamster/.claude/worktrees/anthonygwalters/refactor/claude-zendesk-articles-from-zendesk
rm "$wt/tests/test_zz_zendesk_acceptance.py"
git -C "$wt" status --porcelain
```

Expected: no output.

- [ ] **Step 6: Record the results**

Append to `references/zendesk-api.md` (open with the Read tool first):

```markdown
### Verified live, scratchpad flow

2026-09-30, against `teamschools.zendesk.com`:

- `pull` of article 360035629314 matched every `<img>` to an attachment id;
  `GET /help_center/articles/{id}/attachments.json` returned
  `article_attachments`.
- A throwaway draft (id `<first.article_id>`, archived afterward) uploaded one
  image on create, nothing on a same-folder re-run, and nothing when pulled into
  a fresh folder and published unchanged, with no orphans.
- A translation `PUT` between `pull` and publish changed the article's
  `updated_at`, and the overwrite guard refused.
- The checkout's `git status` was unchanged by the run.
```

Replace `<first.article_id>` with the id printed on line 1. If any observed
result differs from a bullet, write what was observed instead.

Run
`/workspaces/teamster/.trunk/tools/trunk fmt .claude/skills/zendesk-help-articles/references/zendesk-api.md </dev/null 2>&1 | tail -n 3`,
then commit:

```bash
wt=/workspaces/teamster/.claude/worktrees/anthonygwalters/refactor/claude-zendesk-articles-from-zendesk
git -C "$wt" add -u
git -C "$wt" commit -m "docs(zendesk): record the live scratchpad-flow verification" -m "Refs #5628" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
