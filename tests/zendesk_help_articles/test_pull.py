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
