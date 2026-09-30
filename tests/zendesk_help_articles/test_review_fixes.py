"""Tests added from the whole-branch review: local checks before network, state
saved as soon as Zendesk changes, stale attachments pruned, and input hardening."""

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
from test_publish import Server, client_for, write_article

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


def test_removed_image_is_pruned_and_reported(tmp_path):
    d = write_article(
        tmp_path,
        {
            "article_id": 42,
            "last_known_updated_at": "2026-09-29T10:00:00Z",
            "attachments": {"images/gone.png": {"id": 5, "url": "u", "sha256": "h"}},
        },
        html="<p>no images</p>",
    )
    server = Server(
        existing={"id": 42, "updated_at": "2026-09-29T10:00:00Z", "html_url": "u"}
    )
    client, _ = client_for(server)
    result = run(d, client)
    assert result.orphaned_ids == [5]
    assert yaml.safe_load((d / "article.yml").read_text())["attachments"] == {}


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
    assert raw["attachments"]["images/a.png"]["id"] == 101


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
    server = Server(
        existing={"id": 42, "updated_at": "2026-09-29T10:00:00Z", "html_url": "u"}
    )
    client, _ = client_for(server)
    run(d, client)


def test_hand_entered_article_id_without_timestamp_refuses(tmp_path):
    d = write_article(tmp_path, {"article_id": 42})
    server = Server(
        existing={"id": 42, "updated_at": "2026-09-29T10:00:00Z", "html_url": "u"}
    )
    client, session = client_for(server)
    with pytest.raises(PublishError, match="2026-09-29T10:00:00Z"):
        run(d, client)
    assert [m for m, _, _ in session.calls if m in ("PUT", "POST")] == []


def test_live_article_is_not_demoted_without_unpublish(tmp_path):
    d = write_article(
        tmp_path, {"article_id": 42, "last_known_updated_at": "2026-09-29T10:00:00Z"}
    )
    server = Server(
        existing={"id": 42, "updated_at": "2026-09-29T10:00:00Z", "html_url": "u"}
    )
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
    out = rewrite_srcs(html, {"images/a.png": {"url": "https://z/1"}})
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


def test_partial_upload_failure_keeps_uploaded_attachments(tmp_path):
    d = write_article(tmp_path, html='<img src="images/a.png"><img src="images/b.png">')
    (d / "images" / "b.png").write_bytes(b"png2")
    server = Server()
    routes = server.routes()
    real_upload = routes[("POST", "/help_center/articles/42/attachments.json")]

    def second_fails(kw):
        status, payload = real_upload(kw)
        return (500, {"error": "boom"}) if server.uploads == 2 else (status, payload)

    routes[("POST", "/help_center/articles/42/attachments.json")] = second_fails
    client = ZendeskHelpCenter("z", "e", "t", session=FakeSession(routes))
    with pytest.raises(PublishError, match="500"):
        run(d, client, approved_images=frozenset({"images/a.png", "images/b.png"}))
    raw = yaml.safe_load((d / "article.yml").read_text())
    assert raw["attachments"]["images/a.png"]["id"] == 101
    assert "images/b.png" not in raw["attachments"]
