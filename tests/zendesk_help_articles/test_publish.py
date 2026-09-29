from pathlib import Path

import pytest
import yaml
from fakes import FakeSession

# trunk-ignore(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from publish_article import PublishError, ZendeskHelpCenter, publish

SEGMENTS = (200, {"user_segments": [{"id": 11, "name": "Signed-in users"}]})
GROUPS = (200, {"permission_groups": [{"id": 21, "name": "Agents and admins"}]})


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
    """Enough Zendesk state to drive publish() end to end."""

    def __init__(self, existing: dict | None = None):
        self.article = existing
        self.translation = {
            "title": "Old",
            "body": "<p>old</p>",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        self.uploads = 0
        self.article_updates: list[dict] = []
        self.translation_updates: list[dict] = []

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

        def update_article(kw):
            self.article_updates.append(kw["json"]["article"])
            self.article = {
                **(self.article or {}),
                **kw["json"]["article"],
                "updated_at": "2026-09-29T10:05:00Z",
            }
            return 200, {"article": self.article}

        def upload(_):
            self.uploads += 1
            n = 100 + self.uploads
            return 201, {
                "article_attachment": {
                    "id": n,
                    "content_url": f"https://z/hc/article_attachments/{n}/a.png",
                }
            }

        def get_translation(_):
            return 200, {"translation": self.translation}

        def update_translation(kw):
            t = kw["json"]["translation"]
            self.translation_updates.append(t)
            body = t["body"].replace(
                "https://z/hc/article_attachments/101/a.png",
                "/hc/article_attachments/101",
            )
            self.translation = {**t, "body": body, "updated_at": "2026-09-29T10:05:00Z"}
            return 200, {"translation": self.translation}

        return {
            ("GET", "/help_center/user_segments.json"): SEGMENTS,
            ("GET", "/guide/permission_groups.json"): GROUPS,
            ("POST", "/help_center/sections/5/articles.json"): create,
            ("GET", "/help_center/articles/42.json"): get_article,
            ("PUT", "/help_center/articles/42.json"): update_article,
            ("POST", "/help_center/articles/42/attachments.json"): upload,
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


def test_first_publish_creates_draft_uploads_and_saves_state(tmp_path):
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
    methods = [m for m, p, _ in session.calls]
    created = session.calls[methods.index("POST")][2]["json"]["article"]
    assert created["draft"] is True and created["user_segment_id"] == 11
    assert created["permission_group_id"] == 21 and created["author_id"] == 2
    assert server.article_updates[-1]["label_names"] == ["tableau"]
    sent = server.translation_updates[-1]
    assert sent["draft"] is True and sent["title"] == "T"
    assert "https://z/hc/article_attachments/101/a.png" in sent["body"]
    raw = yaml.safe_load((d / "article.yml").read_text())
    assert raw["article_id"] == 42
    assert raw["last_known_updated_at"] == "2026-09-29T10:05:00Z"
    assert raw["attachments"]["images/a.png"]["id"] == 101
    assert 'src="images/a.png"' in (d / "article.html").read_text()


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


def test_existing_article_is_updated_not_recreated_and_backed_up(tmp_path):
    d = write_article(
        tmp_path, {"article_id": 42, "last_known_updated_at": "2026-09-29T10:00:00Z"}
    )
    server = Server(
        existing={
            "id": 42,
            "updated_at": "2026-09-29T10:00:00Z",
            "html_url": "https://z/hc/en-us/articles/42",
        }
    )
    client, session = client_for(server)
    result = publish(
        d,
        live=False,
        approved_images=frozenset({"images/a.png"}),
        backup_dir=tmp_path / "bak",
        client=client,
    )
    assert "POST" not in [m for m, p, _ in session.calls if "sections" in p]
    assert result.backup is not None and result.backup.exists()
    assert "<p>old</p>" in result.backup.read_text()


def test_overwrite_guard_stops_before_any_write(tmp_path):
    d = write_article(
        tmp_path, {"article_id": 42, "last_known_updated_at": "2026-09-29T09:00:00Z"}
    )
    server = Server(
        existing={"id": 42, "updated_at": "2026-09-29T10:00:00Z", "html_url": "u"}
    )
    client, session = client_for(server)
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
