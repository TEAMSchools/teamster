"""Pure-helper coverage for Grow observation-group matching and anchoring.

`_match_observation_group` and `_can_anchor_group` are plain functions over
small dicts -- no Dagster execution, no Grow API, no fixtures beyond literals.
"""

from typing import Any

from teamster.code_locations.kipptaf.level_data.grow.assets import (
    _can_anchor_group,
    _match_observation_group,
)


def test_match_observation_group_exact_name_match() -> None:
    existing_by_id = {"g1": "Teachers", "g2": "Jane Doe (123)"}

    assert (
        _match_observation_group("Teachers", None, existing_by_id, claimed=set())
        == "g1"
    )


def test_match_observation_group_falls_back_to_match_key() -> None:
    """A renamed coach keeps their group's id via the parenthesised employee number."""
    existing_by_id = {"g1": "Jane Doe (123)"}

    # Display name changed from "Jane Doe" to "Jane Smith", but the match key
    # still carries the same "(123)" employee number.
    result = _match_observation_group(
        "Jane Smith (123)", "(123)", existing_by_id, claimed=set()
    )

    assert result == "g1"


def test_match_observation_group_no_fallback_for_none_match_key() -> None:
    """ "Teachers" must not fall back into a same-suffixed "Teachers - Grade 5" group."""
    existing_by_id = {"g1": "Teachers - Grade 5"}

    assert (
        _match_observation_group("Teachers", None, existing_by_id, claimed=set())
        is None
    )


def test_match_observation_group_skips_claimed_ids() -> None:
    existing_by_id = {"g1": "Jane Doe (123)"}

    result = _match_observation_group(
        "Jane Smith (123)", "(123)", existing_by_id, claimed={"g1"}
    )

    assert result is None


def test_match_observation_group_returns_none_when_nothing_matches() -> None:
    existing_by_id = {"g1": "Jane Doe (123)"}

    assert (
        _match_observation_group("John Roe (456)", "(456)", existing_by_id, set())
        is None
    )


def test_match_observation_group_short_employee_number_does_not_match_longer() -> None:
    """Employee 1675 must not match a group belonging to employee 101675.

    Without the opening paren in the match key, "...101675)" would end with
    "1675)" and falsely match.
    """
    existing_by_id = {"g1": "Denn Farquharson (101675)"}

    result = _match_observation_group(
        "New Coach (1675)", "(1675)", existing_by_id, claimed=set()
    )

    assert result is None


def _user(**overrides: Any) -> dict[str, Any]:
    user: dict[str, Any] = {
        "inactive": 0,
        "readonly": 0,
        "group_type": ["observers", "observees"],
    }
    user.update(overrides)

    return user


def test_can_anchor_group_false_when_inactive() -> None:
    assert _can_anchor_group(_user(inactive=1)) is False


def test_can_anchor_group_false_when_readonly() -> None:
    assert _can_anchor_group(_user(readonly=1)) is False


def test_can_anchor_group_false_when_missing_observers_role() -> None:
    assert _can_anchor_group(_user(group_type=["observees"])) is False


def test_can_anchor_group_true_when_active_not_readonly_and_observer() -> None:
    assert _can_anchor_group(_user()) is True
