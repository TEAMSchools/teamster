"""Hand-check selection and results."""

import pytest
import yaml

pytest.importorskip("tableauhyperapi")

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest registers cube_validate at runtime
from cube_validate import cells, handchecks, hyper  # noqa: E402


def _cell(v, sheet="ADA", school="Rise"):
    return cells.Cell("default", sheet, {"School": school}, "ADA", "94.2%", 0.95, v)


def test_pick_covers_every_verdict_and_bucket_then_passes():
    cs = [
        _cell(cells.ROW_GAP),
        _cell(cells.FORMULA_GAP),
        *[_cell(cells.PASS, school=f"S{i}") for i in range(10)],
    ]
    rows = [
        {
            "base": "cube_only",
            "cause": "unexplained",
            "k_student": 1,
            "k_day": "2026-10-06",
        }
    ]
    got = handchecks.pick(cs, rows, seed="snap")
    kinds = [(h.kind, h.title) for h in got]
    assert [k for k, _ in kinds].count("cell") == 5 and [k for k, _ in kinds].count(
        "row"
    ) == 1
    assert any(cells.ROW_GAP in t for _, t in kinds) and any(
        cells.FORMULA_GAP in t for _, t in kinds
    )
    assert handchecks.pick(cs, rows, seed="snap") == got  # deterministic


def test_write_keeps_entered_results(tmp_path):
    hc = [handchecks.HandCheck("C1", "cell", "t", ["s"])]
    handchecks.write(tmp_path, hc, "ZZ-REVIEW x", {}, [])
    y = tmp_path / "hand_checks.yml"
    data = yaml.safe_load(y.read_text())
    data[0]["result"] = "agree"
    y.write_text(yaml.safe_dump(data))
    handchecks.write(tmp_path, hc, "ZZ-REVIEW x", {}, [])
    assert handchecks.read_results(y) == {"C1": "agree"}


def _row(base, cause, student):
    return {"base": base, "cause": cause, "k_student": student, "k_day": "2026-10-06"}


def test_ids_come_from_content_so_a_new_bucket_moves_none():
    cs = [_cell(cells.ROW_GAP), _cell(cells.PASS, school="S1")]
    a = _row("dashboard_only", "unexplained", 1)
    first = handchecks.pick(cs, [a], seed="snap")
    again = handchecks.pick(cs, [_row("cube_only", "unexplained", 2), a], seed="snap")
    ids = {h.title: h.id for h in first}
    assert all(ids[h.title] == h.id for h in again if h.title in ids)
    assert len({h.id for h in again}) == len(again)
    assert all(h.id[:2] in ("C-", "R-") and len(h.id) == 10 for h in again)


def test_read_results_refuses_any_other_value(tmp_path):
    y = tmp_path / "hand_checks.yml"
    y.write_text(
        yaml.safe_dump(
            [
                {"id": "C-1", "result": "agree"},
                {"id": "C-2", "result": "Agree"},
                {"id": "R-3", "result": "pending"},
                {"id": "R-4", "result": "yes"},
            ]
        )
    )
    with pytest.raises(ValueError, match=r"C-2: Agree.*R-4: yes"):
        handchecks.read_results(y)


def test_cell_check_names_when_cubes_answer_was_captured():
    answers = {
        cells.answer_key("default", "ADA"): {"last_refresh": "2026-10-15T20:00:00Z"}
    }
    (h,) = handchecks.pick([_cell(cells.ROW_GAP)], [], seed="s", answers=answers)
    assert (
        "Cube's answer was captured at 2026-10-15T20:00:00Z; compare against that, "
        "not today's Cube." in h.steps
    )


def test_row_samples_quote_a_cause_id_with_an_apostrophe(tmp_path):
    checks = type("C", (), {"student_key": "student", "date_key": "day"})()
    with hyper.Workspace(tmp_path / "s.hyper", {}) as ws:
        ws.execute(
            "create temporary table rows (base text, cause text, "
            '"k_student" bigint, "k_day" text)'
        )
        ws.execute("insert into rows values ('dashboard_only', 'it''s odd', 1, 'd')")
        ws.execute("insert into rows values ('cube_only', null, 2, 'd')")
        got = handchecks.row_samples(ws, checks)
    assert {(r["base"], r["cause"]) for r in got} == {
        ("dashboard_only", "it's odd"),
        ("cube_only", None),
    }


def test_the_cap_is_named_in_what_no_hand_check_covers(tmp_path):
    cs = [_cell(cells.ROW_GAP), _cell(cells.FORMULA_GAP)]
    rows = [_row("dashboard_only", f"cause-{i}", i) for i in range(14)]
    picked = handchecks.pick(cs, rows, seed="snap")
    left = handchecks.uncovered(cs, rows, picked)
    assert len(picked) == 12 and len(left) == 4
    assert all(x.startswith("dashboard_only / cause-") for x in left)
    handchecks.write(tmp_path, picked, "ZZ", {}, left)
    last = (tmp_path / "hand_checks.md").read_text().rstrip().splitlines()[-1]
    assert last.startswith("Not covered by a hand check: ") and left[0] in last


def test_everything_covered_says_so(tmp_path):
    cs = [_cell(cells.ROW_GAP)]
    picked = handchecks.pick(cs, [], seed="s")
    assert handchecks.uncovered(cs, [], picked) == []
    handchecks.write(tmp_path, picked, "ZZ", {}, [])
    text = (tmp_path / "hand_checks.md").read_text()
    assert text.rstrip().endswith("Every verdict and bucket has a hand check.")
