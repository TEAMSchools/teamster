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


def article(**overrides) -> Article:
    base = dict(
        dir=Path("."),
        title="How to access Tableau",
        section_id=1,
        author_id=2,
        user_segment="Signed-in users",
        permission_group="Agents and admins",
        labels=[],
        article_id=42,
        last_known_updated_at="2026-09-29T10:00:00Z",
        attachments={
            "images/a.png": {
                "id": 101,
                "url": "https://z/hc/article_attachments/101/a.png",
                "sha256": "h",
            }
        },
        html="",
    )
    base.update(overrides)
    return Article(**base)


def test_guard_passes_when_timestamps_match():
    check_overwrite_guard({"updated_at": "2026-09-29T10:00:00Z"}, article())


def test_guard_passes_on_first_publish_with_no_known_timestamp():
    check_overwrite_guard(
        {"updated_at": "anything"}, article(last_known_updated_at=None)
    )


def test_guard_aborts_with_both_timestamps():
    with pytest.raises(
        PublishError, match="2026-09-29T10:00:00Z.*2026-09-29T11:30:00Z"
    ):
        check_overwrite_guard({"updated_at": "2026-09-29T11:30:00Z"}, article())


def test_backup_writes_title_and_body_outside_the_repo(tmp_path):
    path = backup_translation(
        {"title": "Old", "body": "<p>old</p>"}, tmp_path, article()
    )
    assert path.parent == tmp_path
    assert path.name.startswith("zendesk-article-42-")
    text = path.read_text()
    assert "Old" in text and "<p>old</p>" in text


def test_readback_matches_attachments_by_id_after_url_shortening():
    stored = {
        "title": "How to access Tableau",
        "body": '<img src="/hc/article_attachments/101">',
    }
    verify_readback(stored, article())


def test_readback_fails_on_missing_attachment():
    stored = {"title": "How to access Tableau", "body": "<p>no image</p>"}
    with pytest.raises(PublishError, match="101"):
        verify_readback(stored, article())


def test_readback_fails_on_title_mismatch():
    stored = {"title": "Other", "body": '<img src="/hc/article_attachments/101">'}
    with pytest.raises(PublishError, match="title"):
        verify_readback(stored, article())
