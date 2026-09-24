"""Tests for scripts/cube_rls_matrix.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path(__file__).parents[1] / "scripts" / "cube_rls_matrix.py"
_MODULE_NAME = "cube_rls_matrix"
_UNRESOLVABLE = "unresolvable@ktaf-sandbox.invalid"


def _load_script():
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Registration before exec_module is required for the module's @dataclass
    # (CubeConnection) to resolve its own forward-referenced type.
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


def test_script_module_loads() -> None:
    assert _load_script() is not None


# --- load_viewers ---------------------------------------------------------


def test_load_viewers_returns_explicit_list_unchanged() -> None:
    mod = _load_script()
    assert mod.load_viewers(["a@x.org", "b@x.org"], None) == ["a@x.org", "b@x.org"]


def test_load_viewers_reads_file_skips_blanks_and_comments(tmp_path) -> None:
    mod = _load_script()
    viewers_file = tmp_path / "viewers.txt"
    viewers_file.write_text(
        "a@x.org\n\n# a full-line comment\n   b@x.org   \n   \n#c@x.org\n",
        encoding="utf-8",
    )
    assert mod.load_viewers(None, viewers_file) == ["a@x.org", "b@x.org"]


def test_load_viewers_file_all_blank_or_comment_returns_empty(tmp_path) -> None:
    mod = _load_script()
    viewers_file = tmp_path / "viewers.txt"
    viewers_file.write_text("\n# nothing here\n   \n", encoding="utf-8")
    assert mod.load_viewers(None, viewers_file) == []


# --- run_for_viewer: error handling (Task 1) ------------------------------


def _connection(**overrides) -> object:
    mod = sys.modules[_MODULE_NAME]
    defaults = {
        "host": "127.0.0.1",
        "port": 15432,
        "dbname": "cube",
        "password": "pw",
        "query": "SELECT 1",
    }
    defaults.update(overrides)
    return mod.CubeConnection(**defaults)


def test_run_for_viewer_empty_error_message_falls_back_to_placeholder(
    monkeypatch,
) -> None:
    mod = _load_script()

    def _raise_empty(*_args, **_kwargs):
        raise mod.psycopg.OperationalError("")

    monkeypatch.setattr(mod.psycopg, "connect", _raise_empty)
    rows, error = mod.run_for_viewer("a@x.org", _connection())
    assert rows == []
    assert error == "unknown error"


def test_run_for_viewer_multiline_error_returns_first_line_only(monkeypatch) -> None:
    mod = _load_script()

    def _raise_multiline(*_args, **_kwargs):
        raise mod.psycopg.OperationalError("connection refused\ndetail: nope\n")

    monkeypatch.setattr(mod.psycopg, "connect", _raise_multiline)
    rows, error = mod.run_for_viewer("a@x.org", _connection())
    assert rows == []
    assert error == "connection refused"


# --- main(): exit status (Task 2) -----------------------------------------
#
# run_for_viewer is monkeypatched per-viewer so no socket is ever opened;
# everything else (arg parsing, aggregation, diagnostics, exit code) runs for
# real, so these assert genuine main() return values, not mock call counts.


def test_main_missing_password_returns_nonzero_without_connecting(monkeypatch) -> None:
    mod = _load_script()
    monkeypatch.delenv("CUBEJS_SQL_PASSWORD", raising=False)
    monkeypatch.setattr(sys, "argv", ["cube_rls_matrix.py", "--viewers", "a@x.org"])

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("run_for_viewer should not be called without a password")

    monkeypatch.setattr(mod, "run_for_viewer", _fail_if_called)
    assert mod.main() == 1


def test_main_success_path_returns_zero(monkeypatch) -> None:
    mod = _load_script()
    monkeypatch.setattr(
        sys,
        "argv",
        ["cube_rls_matrix.py", "--viewers", "a@x.org", "b@x.org", "--password", "pw"],
    )
    responses = {
        "a@x.org": ([("Newark", 10)], None),
        "b@x.org": ([("Camden", 5)], None),
    }
    monkeypatch.setattr(
        mod, "run_for_viewer", lambda viewer, connection: responses[viewer]
    )
    assert mod.main() == 0


def test_main_all_viewers_zero_rows_returns_nonzero(monkeypatch, capsys) -> None:
    mod = _load_script()
    monkeypatch.setattr(
        sys,
        "argv",
        ["cube_rls_matrix.py", "--viewers", "a@x.org", "b@x.org", "--password", "pw"],
    )
    monkeypatch.setattr(mod, "run_for_viewer", lambda viewer, connection: ([], None))
    assert mod.main() == 1
    assert "EVERY viewer returned 0 rows" in capsys.readouterr().out


def test_main_single_viewer_zero_rows_returns_zero(monkeypatch, capsys) -> None:
    """A single viewer at 0 rows is a legitimate default-deny check (e.g. a
    `none`-scope viewer), not a failure - the all-zero gate must NOT fire with
    just one viewer, since the cross-viewer comparison it exists for needs 2+
    viewers to mean anything."""
    mod = _load_script()
    monkeypatch.setattr(
        sys,
        "argv",
        ["cube_rls_matrix.py", "--viewers", "a@x.org", "--password", "pw"],
    )
    monkeypatch.setattr(mod, "run_for_viewer", lambda viewer, connection: ([], None))
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "0 rows for the single viewer checked" in out
    assert "EVERY viewer returned 0 rows" not in out


def test_main_connection_failures_still_return_nonzero(monkeypatch) -> None:
    """Unchanged behavior: a hard connection failure fails the gate too."""
    mod = _load_script()
    monkeypatch.setattr(
        sys,
        "argv",
        ["cube_rls_matrix.py", "--viewers", "a@x.org", "b@x.org", "--password", "pw"],
    )

    def _fake_run(viewer, _connection):
        if viewer == "a@x.org":
            return [], "connection refused"
        return [("Newark", 10)], None

    monkeypatch.setattr(mod, "run_for_viewer", _fake_run)
    assert mod.main() == 1


def test_main_identical_fingerprints_warns_but_stays_zero_exit(
    monkeypatch, capsys
) -> None:
    """More than one viewer with identical rows is flagged as suspicious but is not
    automatically wrong (two viewers can legitimately share one scope), so the
    ordinary success exit status is preserved - only the diagnostic changes."""
    mod = _load_script()
    monkeypatch.setattr(
        sys,
        "argv",
        ["cube_rls_matrix.py", "--viewers", "a@x.org", "b@x.org", "--password", "pw"],
    )
    same_rows = [("Newark", 10)]
    monkeypatch.setattr(
        mod, "run_for_viewer", lambda viewer, connection: (same_rows, None)
    )
    assert mod.main() == 0
    assert "EVERY viewer returned IDENTICAL rows" in capsys.readouterr().out


# --- canary assertions ----------------------------------------------------

_CANARIES = Path(__file__).parents[1] / "src" / "cube" / "sandbox" / "canaries.yml"
_PERSONAS = Path(__file__).parents[1] / "src" / "cube" / "sandbox" / "personas.yml"


def test_zero_rows_does_not_satisfy_blocked() -> None:
    mod = _load_script()
    # This one distinction is what forces production-mode sign-off: a dev-mode
    # runner returns zero rows where production denies, and treating that as a
    # pass reports a falsely benign matrix.
    assert not mod.expectation_met("BLOCKED", rows=[], error=None)
    assert mod.expectation_met(
        "BLOCKED", rows=[], error="Table or CTE with name 'x' not found"
    )
    assert mod.expectation_met("ZERO", rows=[], error=None)
    assert not mod.expectation_met("ZERO", rows=[("a",)], error=None)
    assert mod.expectation_met("ROWS", rows=[("a",)], error=None)


def test_blocked_requires_the_real_denial_not_any_not_found() -> None:
    mod = _load_script()
    # A column- or dataset-not-found error is a broken query, not a denial.
    # Accepting it would let a canary go green on a typo.
    assert not mod.expectation_met(
        "BLOCKED", rows=[], error="Column 'nope' not found in view"
    )
    assert not mod.expectation_met("BLOCKED", rows=[], error="connection refused")


def test_rows_and_zero_are_failures_when_the_query_errored() -> None:
    mod = _load_script()
    assert not mod.expectation_met("ROWS", rows=[("a",)], error="boom")
    assert not mod.expectation_met("ZERO", rows=[], error="boom")


def test_an_unknown_expectation_raises() -> None:
    mod = _load_script()
    with pytest.raises(ValueError, match="unknown expectation"):
        mod.expectation_met("MAYBE", rows=[], error=None)


def test_the_committed_canaries_load_and_are_well_formed() -> None:
    mod = _load_script()
    canaries = mod.load_canaries(_CANARIES)
    assert canaries
    assert all(c.expect in mod.EXPECTATIONS for c in canaries)
    assert all(c.why for c in canaries), "every canary states why it should hold"


def test_a_blocked_only_suite_is_rejected(tmp_path) -> None:
    mod = _load_script()
    # Every view reports "not found" for everyone against an empty compiled
    # schema (a misconfigured CUBEJS_SCHEMA_PATH does exactly that), so a
    # BLOCKED-only suite goes green on a deployment that denies the world —
    # which looks identical to perfect isolation.
    path = tmp_path / "canaries.yml"
    path.write_text(
        "canaries:\n"
        "  - persona: a@ktaf-sandbox.invalid\n"
        "    query_shape: SELECT 1\n"
        "    expect: BLOCKED\n"
        "    why: because\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no ROWS canary"):
        mod.load_canaries(path)


def test_an_unknown_expectation_in_the_file_is_rejected(tmp_path) -> None:
    mod = _load_script()
    path = tmp_path / "canaries.yml"
    path.write_text(
        "canaries:\n"
        "  - persona: a@ktaf-sandbox.invalid\n"
        "    query_shape: SELECT 1\n"
        "    expect: PROBABLY\n"
        "    why: because\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown expectation"):
        mod.load_canaries(path)


def test_every_canary_persona_is_declared_or_deliberately_absent() -> None:
    mod = _load_script()
    declared = {p["email"] for p in yaml.safe_load(_PERSONAS.read_text())["personas"]}
    for canary in mod.load_canaries(_CANARIES):
        assert canary.persona in declared or canary.persona == _UNRESOLVABLE, (
            f"{canary.persona} is neither declared nor the unresolvable identity"
        )


def test_every_declared_persona_is_exercised_by_a_canary() -> None:
    # A persona nothing queries as tests nothing. The manifest requires each
    # scope value to exist as a row; the canaries are what prove the policy
    # built on it actually resolves.
    mod = _load_script()
    declared = {p["email"] for p in yaml.safe_load(_PERSONAS.read_text())["personas"]}
    exercised = {c.persona for c in mod.load_canaries(_CANARIES)}
    assert declared - exercised == set()


def test_the_unresolvable_identity_is_never_declared() -> None:
    # Its whole purpose is to have no dim_staff_cube_access row, which
    # exercises clean default-deny for an identity the warehouse has never
    # heard of.
    declared = {p["email"] for p in yaml.safe_load(_PERSONAS.read_text())["personas"]}
    assert _UNRESOLVABLE not in declared
