from pathlib import Path

import pytest
from fakes import FakeSession

# trunk-ignore(pyright/reportMissingImports): conftest.py puts the scripts folder on sys.path
from publish_article import Article, PublishError, ZendeskHelpCenter, resolve_visibility

SEGMENTS = {
    "user_segments": [
        {"id": 11, "name": "Signed-in users"},
        {"id": 12, "name": "Staff"},
    ]
}
GROUPS = {
    "permission_groups": [
        {"id": 21, "name": "Agents and admins"},
        {"id": 22, "name": "Data"},
    ]
}


def client():
    return ZendeskHelpCenter(
        "s",
        "e",
        "t",
        session=FakeSession(
            {
                ("GET", "/help_center/user_segments.json"): (200, SEGMENTS),
                ("GET", "/guide/permission_groups.json"): (200, GROUPS),
            }
        ),
    )


def article(user_segment="Signed-in users", permission_group="Agents and admins"):
    return Article(
        dir=Path("."),
        title="T",
        section_id=1,
        author_id=2,
        user_segment=user_segment,
        permission_group=permission_group,
        labels=[],
        article_id=None,
        last_known_updated_at=None,
        attachments={},
        html="",
    )


def test_defaults_resolve_to_ids():
    assert resolve_visibility(client(), article()) == (11, 21)


def test_override_names_resolve():
    assert resolve_visibility(client(), article("Staff", "Data")) == (12, 22)


def test_unknown_segment_refuses_and_lists_choices():
    with pytest.raises(PublishError, match="Signed in users.*Signed-in users.*Staff"):
        resolve_visibility(client(), article("Signed in users"))


def test_unknown_group_refuses():
    with pytest.raises(PublishError, match="Nobody"):
        resolve_visibility(client(), article(permission_group="Nobody"))


def test_everyone_is_only_reachable_by_literal():
    assert resolve_visibility(client(), article("everyone")) == (None, 21)
