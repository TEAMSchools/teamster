"""Hand-check selection and results."""

import yaml

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest registers cube_validate at runtime
from cube_validate import cells, handchecks  # noqa: E402


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
    handchecks.write(tmp_path, hc, "ZZ-REVIEW x", {})
    y = tmp_path / "hand_checks.yml"
    data = yaml.safe_load(y.read_text())
    data[0]["result"] = "agree"
    y.write_text(yaml.safe_dump(data))
    handchecks.write(tmp_path, hc, "ZZ-REVIEW x", {})
    assert handchecks.read_results(y) == {"C1": "agree"}
