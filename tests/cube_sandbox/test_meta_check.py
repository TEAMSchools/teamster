from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from teamster.cube_sandbox import meta_check

# Long enough for HS256 and deliberately low-entropy, so no scanner reads it
# as a real credential.
FAKE_SECRET = "not-a-real-secret-" * 2

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


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------


def test_fetch_meta_signs_the_identity_and_sends_the_raw_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The auth path documented in src/cube/CLAUDE.md, not a guess at one.

    The entire JWT payload IS the security context, so the top-level `email`
    claim is what `checkAuth` reads, and the header carries the raw token —
    a `Bearer` prefix is rejected.
    """
    import jwt
    import requests

    captured: dict[str, Any] = {}

    class _Response:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"cubes": []}

    def fake_get(url: str, headers: dict, timeout: int) -> _Response:
        captured["url"] = url
        captured["headers"] = headers
        return _Response()

    monkeypatch.setattr(requests, "get", fake_get)

    meta_check.fetch_meta("https://sandbox.example.invalid/", FAKE_SECRET)

    assert captured["url"] == "https://sandbox.example.invalid/v1/meta"
    token = captured["headers"]["Authorization"]
    assert not token.startswith("Bearer ")
    claims = jwt.decode(token, FAKE_SECRET, algorithms=["HS256"])
    assert claims["email"] == meta_check.DEFAULT_VIEWER
    # jwt.verify enforces maxAge from `iat`; a token without one is rejected.
    assert "iat" in claims


def test_a_missing_pinned_catalog_says_so(tmp_path: Path) -> None:
    # Comparing against a catalog this check invented would prove only that
    # the deployment matches itself.
    with pytest.raises(SystemExit, match="no pinned catalog"):
        meta_check.load_catalog(tmp_path / "absent.json")


def test_the_check_refuses_to_guess_a_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (meta_check.REST_URL, meta_check.API_SECRET):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(SystemExit, match=meta_check.REST_URL):
        meta_check.main([])
