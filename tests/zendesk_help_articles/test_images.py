from pathlib import Path

import pytest
from fakes import FakeSession

# trunk-ignore(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from publish_article import (
    Article,
    PublishError,
    ZendeskHelpCenter,
    local_images,
    rewrite_srcs,
    sha256_of,
    sync_attachments,
)

HTML = (
    '<img src="images/a.png" alt="a">'
    '<img alt="b" src="images/b.png">'
    '<img src="https://cdn.example.org/x.png">'
    '<img src="images/a.png">'
)


def test_local_images_skips_absolute_and_dedupes():
    assert local_images(HTML) == ["images/a.png", "images/b.png"]


def test_rewrite_srcs_replaces_only_known_relative_paths():
    out = rewrite_srcs(
        HTML, {"images/a.png": {"url": "https://z/hc/article_attachments/1"}}
    )
    assert out.count("https://z/hc/article_attachments/1") == 2
    assert 'src="images/b.png"' in out
    assert 'src="https://cdn.example.org/x.png"' in out


def make(tmp_path: Path, html: str, attachments: dict | None = None) -> Article:
    (tmp_path / "images").mkdir(exist_ok=True)
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
        attachments=attachments or {},
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
        sync_attachments(upload_client(calls), a, frozenset({"images/missing.png"}))
    assert calls == []


def test_unapproved_image_refuses_before_upload(tmp_path):
    a = make(tmp_path, '<img src="images/a.png">')
    (tmp_path / "images" / "a.png").write_bytes(b"1")
    calls: list[int] = []
    with pytest.raises(PublishError, match="PII gate.*images/a.png"):
        sync_attachments(upload_client(calls), a, frozenset())
    assert calls == []


def test_new_image_uploads_and_records(tmp_path):
    a = make(tmp_path, '<img src="images/a.png">')
    (tmp_path / "images" / "a.png").write_bytes(b"1")
    calls: list[int] = []
    report = sync_attachments(upload_client(calls), a, frozenset({"images/a.png"}))
    assert report.uploaded == ["images/a.png"]
    assert a.attachments["images/a.png"] == {
        "id": 101,
        "url": "https://z/hc/article_attachments/101",
        "sha256": sha256_of(tmp_path / "images" / "a.png"),
    }


def test_unchanged_image_is_reused_without_upload(tmp_path):
    (tmp_path / "images").mkdir()
    img = tmp_path / "images" / "a.png"
    img.write_bytes(b"1")
    a = make(
        tmp_path,
        '<img src="images/a.png">',
        {"images/a.png": {"id": 5, "url": "u", "sha256": sha256_of(img)}},
    )
    calls: list[int] = []
    report = sync_attachments(upload_client(calls), a, frozenset())
    assert report.reused == ["images/a.png"]
    assert calls == []


def test_changed_image_reuploads_and_reports_orphan(tmp_path):
    (tmp_path / "images").mkdir()
    img = tmp_path / "images" / "a.png"
    img.write_bytes(b"2")
    a = make(
        tmp_path,
        '<img src="images/a.png">',
        {"images/a.png": {"id": 5, "url": "u", "sha256": "stale"}},
    )
    calls: list[int] = []
    report = sync_attachments(upload_client(calls), a, frozenset({"images/a.png"}))
    assert report.uploaded == ["images/a.png"]
    assert report.orphaned_ids == [5]
    assert a.attachments["images/a.png"]["id"] == 101


def test_absolute_src_is_never_uploaded(tmp_path):
    a = make(tmp_path, '<img src="https://cdn.example.org/x.png">')
    calls: list[int] = []
    report = sync_attachments(upload_client(calls), a, frozenset())
    assert report.uploaded == [] and calls == []
