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
    existing_by_id = {"g1": "Teachers", "g2": "Coach 123 - Jane Doe"}

    assert _match_observation_group("Teachers", existing_by_id, claimed=set()) == "g1"


def test_match_observation_group_falls_back_to_coach_prefix() -> None:
    """A renamed coach keeps their group's id via the employee-number prefix."""
    existing_by_id = {"g1": "Coach 123 - Jane Doe"}

    # Display name changed from "Jane Doe" to "Jane Smith", but the wanted
    # name still carries the same "Coach 123 - " prefix.
    result = _match_observation_group(
        "Coach 123 - Jane Smith", existing_by_id, claimed=set()
    )

    assert result == "g1"


def test_match_observation_group_no_fallback_for_non_coach_name() -> None:
    """ "Teachers" must not fall back into a same-prefixed "Teachers - ..." group."""
    existing_by_id = {"g1": "Teachers - Grade 5"}

    assert _match_observation_group("Teachers", existing_by_id, claimed=set()) is None


def test_match_observation_group_skips_claimed_ids() -> None:
    existing_by_id = {"g1": "Coach 123 - Jane Doe"}

    result = _match_observation_group(
        "Coach 123 - Jane Smith", existing_by_id, claimed={"g1"}
    )

    assert result is None


def test_match_observation_group_returns_none_when_nothing_matches() -> None:
    existing_by_id = {"g1": "Coach 123 - Jane Doe"}

    assert (
        _match_observation_group("Coach 456 - John Roe", existing_by_id, set()) is None
    )


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
