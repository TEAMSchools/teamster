"""Tests for scripts/cube_rls_matrix.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).parents[1] / "scripts" / "cube_rls_matrix.py"
_MODULE_NAME = "cube_rls_matrix"


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
