from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts/check_sql_banned_syntax.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_sql_banned_syntax", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_sql_banned_syntax"] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


def codes(sql: str) -> list:
    return [hit[2] for hit in mod.find_banned(sql)]


def test_qualify_flagged_with_position() -> None:
    sql = "select a,\nfrom t\nqualify row_number() over (partition by a) = 1\n"
    assert mod.find_banned(sql) == [
        (3, 1, "S1-qualify", "qualify is banned; rank in a CTE, filter with where")
    ]


def test_uppercase_qualify_flagged() -> None:
    assert codes("select a, from t QUALIFY rn = 1") == ["S1-qualify"]


def test_group_by_all_flagged() -> None:
    assert codes("select a, count(*) as n, from t group by all") == ["S1-group-by-all"]


def test_group_by_all_across_lines_flagged() -> None:
    assert codes("select a, from t\ngroup by\n    all\n") == ["S1-group-by-all"]


def test_corresponding_flagged() -> None:
    assert codes("select a, from x full union all corresponding select a, from y") == [
        "S1-corresponding"
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "select a, -- qualify group by all corresponding\nfrom t",
        "select a, {# qualify row_number() = 1 #} from t",
        "select a, {#- multi\nline qualify -#} from t",
        "select 'qualify' as a, \"group by all\" as b, from t",
        "select is_qualifying, corresponding_id, from t",
        "select a, /* qualify */ from t",
        "select a, from t group by all_students",
    ],
)
def test_lookalikes_not_flagged(sql: str) -> None:
    assert codes(sql) == []


def test_positions_survive_comment_blanking() -> None:
    sql = "select a, {# a\nlong comment #} b,\nfrom t qualify rn = 1"
    assert mod.find_banned(sql)[0][:2] == (3, 8)


def test_cli_prints_and_exits_nonzero(tmp_path: Path, capsys) -> None:
    f = tmp_path / "m.sql"
    f.write_text("select a, from t\nqualify rn = 1\n")
    assert mod.main([str(f)]) == 1
    out = capsys.readouterr().out
    assert out == (
        f"{f}:2:1: [error] qualify is banned; rank in a CTE, filter with where"
        " (S1-qualify)\n"
    )


def test_cli_clean_file_exits_zero(tmp_path: Path) -> None:
    f = tmp_path / "m.sql"
    f.write_text("select a, from t where rn = 1\n")
    assert mod.main([str(f)]) == 0
