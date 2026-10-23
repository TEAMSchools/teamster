"""Decisions relabel only the formula-gap cells their evidence covers."""

from dataclasses import replace

# trunk-ignore(pyright/reportAttributeAccessIssue)
from cube_validate import cells, config, decisions, probes  # noqa: E402

from .test_cells import _checks as base_checks  # noqa: E402


def _decision(**over):
    base = dict(
        measure="ADA",
        param=None,
        owner="dashboard",
        rule="the dashboard counts excused days",
        probe="p1",
        cuts=(),
        sheets=(),
        task="",
    )
    base.update(over)
    return config.Decision(**base)


def _checks(*ds):
    return replace(
        base_checks(),
        cuts=(config.Cut("default"), config.Cut("other")),
        decisions=tuple(ds),
    )


def _cell(school="A", verdict=cells.FORMULA_GAP, cut="default", **over):
    base = dict(
        cut=cut,
        sheet="ADA",
        dims={"School": school},
        measure="ADA",
        tableau="33.3%",
        cube=0.5,
        verdict=verdict,
    )
    base.update(over)
    return cells.Cell(**base)


def _result(proven, matching, schools=("A", "B", "C")):
    return probes.ProbeResult(
        "p1",
        proven,
        [
            probes.ProbeCell(
                "default", "ADA", {"School": s}, 0.3, 0.5, True, s in matching
            )
            for s in schools
        ],
    )


def _verdicts(cs):
    return [c.verdict for c in cs]


def test_a_proven_probe_relabels_only_the_cells_it_explains():
    cs = [_cell("A"), _cell("B"), _cell("C")]
    got, summary = decisions.apply(
        _checks(_decision()), cs, [_result(True, ("A", "B"))]
    )
    assert _verdicts(got) == [
        cells.FIX_DASHBOARD,
        cells.FIX_DASHBOARD,
        cells.FORMULA_GAP,
    ]
    assert got[0].reason == "the dashboard counts excused days"
    assert summary == [
        {
            "decision": "ADA (dashboard)",
            "owner": "dashboard",
            "relabeled": 2,
            "still_formula_gap": 1,
            "resolved": 0,
            "probe_proven": True,
        }
    ]


def test_an_unproven_probe_relabels_nothing():
    cs = [_cell("A"), _cell("B")]
    got, summary = decisions.apply(
        _checks(_decision(owner="cube")), cs, [_result(False, ("A", "B"))]
    )
    assert _verdicts(got) == [cells.FORMULA_GAP] * 2
    assert summary[0]["relabeled"] == 0 and not summary[0]["probe_proven"]


def test_an_accepted_decision_covers_only_its_cuts():
    cs = [_cell("A", cut="default"), _cell("A", cut="other")]
    d = _decision(owner="accepted", probe=None, cuts=("other",))
    got, summary = decisions.apply(_checks(d), cs, [])
    assert _verdicts(got) == [cells.FORMULA_GAP, cells.ACCEPTED]
    assert summary[0]["relabeled"] == 1


def test_passing_cells_under_a_decision_count_as_resolved():
    cs = [_cell("A"), _cell("B", verdict=cells.PASS)]
    got, summary = decisions.apply(
        _checks(_decision()), cs, [_result(True, ("A", "B"))]
    )
    assert _verdicts(got) == [cells.FIX_DASHBOARD, cells.PASS]
    assert summary[0]["resolved"] == 1


def test_row_gaps_are_never_relabeled():
    cs = [_cell("A", verdict=cells.ROW_GAP)]
    d = _decision(owner="accepted", probe=None, cuts=("default",))
    got, summary = decisions.apply(_checks(d), cs, [])
    assert _verdicts(got) == [cells.ROW_GAP]
    assert summary[0]["relabeled"] == 0


def test_a_param_decision_names_its_value_and_skips_other_cuts():
    checks = replace(
        _checks(
            _decision(
                param=("Mode", "ADA"), owner="accepted", probe=None, sheets=("ADA",)
            )
        ),
        cuts=(config.Cut("default", params={"Mode": "ADA"}), config.Cut("other")),
    )
    cs = [_cell("A", cut="default"), _cell("A", cut="other")]
    got, summary = decisions.apply(checks, cs, [])
    assert _verdicts(got) == [cells.ACCEPTED, cells.FORMULA_GAP]
    assert summary[0]["decision"] == "ADA / Mode = ADA (accepted)"


def test_a_pass_is_resolved_only_where_the_proven_candidate_matches_cube():
    cs = [_cell("A", verdict=cells.PASS), _cell("B", verdict=cells.PASS)]
    _, summary = decisions.apply(_checks(_decision()), cs, [_result(True, ("A",))])
    assert summary[0]["resolved"] == 1
    _, summary = decisions.apply(_checks(_decision()), cs, [_result(False, ("A", "B"))])
    assert summary[0]["resolved"] == 0
    _, summary = decisions.apply(_checks(_decision()), cs, [])
    assert summary[0]["resolved"] == 0
