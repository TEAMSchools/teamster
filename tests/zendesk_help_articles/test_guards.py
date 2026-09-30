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
        PublishError,
        match="Overwrite guard.*2026-09-29T10:00:00Z.*2026-09-29T11:30:00Z",
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
