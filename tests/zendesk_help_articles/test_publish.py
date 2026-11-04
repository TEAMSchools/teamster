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
