import pytest
from fakes import FakeSession

# trunk-ignore(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from publish_article import PublishError, ZendeskHelpCenter, client_from_environment


def make_client(routes) -> tuple[ZendeskHelpCenter, FakeSession]:
    session = FakeSession(routes)
    return ZendeskHelpCenter("sub", "me@example.org", "tok", session=session), session


def test_auth_is_email_slash_token_basic_auth():
    client, session = make_client({})
    assert session.auth == ("me@example.org/token", "tok")
    assert client.base == "https://sub.zendesk.com/api/v2"


def test_user_segments_unwraps_list():
    client, _ = make_client(
        {
            ("GET", "/help_center/user_segments.json"): (
                200,
                {"user_segments": [{"id": 1}]},
            )
        }
    )
    assert client.user_segments() == [{"id": 1}]


def test_permission_groups_hits_guide_endpoint():
    client, session = make_client(
        {
            ("GET", "/guide/permission_groups.json"): (
                200,
                {"permission_groups": [{"id": 7}]},
            )
        }
    )
    assert client.permission_groups() == [{"id": 7}]
    assert session.paths("GET") == ["/guide/permission_groups.json"]


def test_create_article_posts_to_section_with_notify_off():
    client, session = make_client(
        {
            ("POST", "/help_center/sections/5/articles.json"): (
                201,
                {"article": {"id": 42}},
            )
        }
    )
    assert client.create_article(5, {"title": "T"}) == {"id": 42}
    _, _, kwargs = session.calls[0]
    assert kwargs["json"] == {"article": {"title": "T"}, "notify_subscribers": False}


def test_translation_endpoints_use_en_us():
    client, session = make_client(
        {
            ("GET", "/help_center/articles/42/translations/en-us.json"): (
                200,
                {"translation": {"body": "b"}},
            ),
            ("PUT", "/help_center/articles/42/translations/en-us.json"): (
                200,
                {"translation": {"body": "c"}},
            ),
        }
    )
    assert client.get_translation(42) == {"body": "b"}
    assert client.update_translation(42, {"body": "c"}) == {"body": "c"}
    assert session.calls[1][2]["json"] == {"translation": {"body": "c"}}


def test_upload_attachment_sends_multipart_inline(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG")
    client, session = make_client(
        {
            ("POST", "/help_center/articles/42/attachments.json"): (
                201,
                {"article_attachment": {"id": 9, "content_url": "u"}},
            )
        }
    )
    assert client.upload_attachment(42, img) == {"id": 9, "content_url": "u"}
    _, _, kwargs = session.calls[0]
    assert kwargs["data"] == {"inline": "true"}
    name, handle, mime = kwargs["files"]["file"]
    assert name == "a.png"
    assert mime == "image/png"
    handle.close()


def test_http_error_becomes_publish_error_with_body():
    client, _ = make_client(
        {("GET", "/help_center/articles/1.json"): (422, {"error": "RecordInvalid"})}
    )
    with pytest.raises(PublishError, match="422.*RecordInvalid"):
        client.get_article(1)


def test_client_from_environment_reads_three_vars(monkeypatch):
    monkeypatch.setenv("ZENDESK_SUBDOMAIN", "sub")
    monkeypatch.setenv("ZENDESK_EMAIL", "e")
    monkeypatch.setenv("ZENDESK_TOKEN", "t")
    client = client_from_environment()
    assert client.base == "https://sub.zendesk.com/api/v2"
    assert client.session.auth == ("e/token", "t")


def test_client_from_environment_refuses_when_missing(monkeypatch):
    monkeypatch.delenv("ZENDESK_TOKEN", raising=False)
    monkeypatch.setenv("ZENDESK_SUBDOMAIN", "sub")
    monkeypatch.setenv("ZENDESK_EMAIL", "e")
    with pytest.raises(PublishError, match="ZENDESK_TOKEN"):
        client_from_environment()
