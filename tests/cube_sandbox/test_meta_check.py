from __future__ import annotations

from teamster.cube_sandbox import meta_check

CATALOG = {
    "cubes": [
        {
            "name": "v",
            "measures": [{"name": "v.a", "type": "number"}],
            "dimensions": [{"name": "v.d", "type": "string"}],
        }
    ]
}


def test_an_identical_deployment_diffs_empty() -> None:
    assert meta_check.member_diff(CATALOG, CATALOG) == {
        "added": [],
        "removed": [],
        "retyped": [],
    }
    assert meta_check.exit_code(meta_check.member_diff(CATALOG, CATALOG)) == 0


def test_a_missing_member_is_reported() -> None:
    # This proves the deployed model is the pinned model. It proves nothing
    # about the data: /meta is compiled from the model and never reads the
    # warehouse.
    live = {"cubes": [{"name": "v", "measures": [], "dimensions": []}]}
    assert meta_check.member_diff(live, CATALOG) == {
        "added": [],
        "removed": ["v.a", "v.d"],
        "retyped": [],
    }
    assert meta_check.exit_code(meta_check.member_diff(live, CATALOG)) == 1


def test_an_extra_member_fails_as_loudly_as_a_missing_one() -> None:
    # The sandbox is pinned BEHIND main, so a deploy from the wrong checkout
    # shows up as members the pinned catalog has not got yet. Tolerating
    # additions would let exactly that failure through.
    live = {
        "cubes": [
            {
                "name": "v",
                "measures": [
                    {"name": "v.a", "type": "number"},
                    {"name": "v.b", "type": "number"},
                ],
                "dimensions": [{"name": "v.d", "type": "string"}],
            }
        ]
    }
    diff = meta_check.member_diff(live, CATALOG)
    assert diff == {"added": ["v.b"], "removed": [], "retyped": []}
    assert meta_check.exit_code(diff) == 1


def test_dimensions_count_as_members_too() -> None:
    live = {
        "cubes": [
            {
                "name": "v",
                "measures": [{"name": "v.a", "type": "number"}],
                "dimensions": [
                    {"name": "v.d", "type": "string"},
                    {"name": "v.e", "type": "string"},
                ],
            }
        ]
    }
    assert meta_check.member_diff(live, CATALOG)["added"] == ["v.e"]


def test_an_empty_deployment_reports_every_member_missing() -> None:
    # A deploy that silently did not take, or one against an empty compiled
    # schema, is the failure nobody notices.
    diff = meta_check.member_diff({"cubes": []}, CATALOG)
    assert diff["removed"] == ["v.a", "v.d"]
    assert meta_check.exit_code(diff) == 1


def test_describe_names_both_directions() -> None:
    live = {
        "cubes": [
            {
                "name": "v",
                "measures": [{"name": "v.b", "type": "number"}],
                "dimensions": [],
            }
        ]
    }
    text = meta_check.describe(meta_check.member_diff(live, CATALOG))
    assert "v.a" in text
    assert "v.b" in text


def test_describe_says_so_when_they_match() -> None:
    assert "matches" in meta_check.describe(meta_check.member_diff(CATALOG, CATALOG))


def test_a_retype_is_its_own_category_and_fails() -> None:
    # Keyed by name alone this diffed EMPTY: the member is on both sides, so
    # neither added nor removed fired and the check went green on a model
    # that is not the pinned one. A retype is also the change most likely to
    # break a kit silently — the member still exists and the query still
    # compiles.
    live = {
        "cubes": [
            {
                "name": "v",
                "measures": [{"name": "v.a", "type": "number"}],
                "dimensions": [{"name": "v.d", "type": "number"}],
            }
        ]
    }
    diff = meta_check.member_diff(live, CATALOG)
    assert diff == {
        "added": [],
        "removed": [],
        "retyped": ["v.d: string -> number"],
    }
    assert meta_check.exit_code(diff) == 1
    assert "v.d: string -> number" in meta_check.describe(diff)
