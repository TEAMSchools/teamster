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
        upload_local_images(upload_client(calls), a, frozenset({"images/missing.png"}))
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
