# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import cli, describe

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, Decision, ViewConfig

SCHOOL = Comparison(
    id="mastery-school",
    measure="pct_proficient",
    dims=[ColumnPair("school", "abbreviation")],
    workbook="DDI Suite",
)
REGION = Comparison(
    id="mastery-region",
    measure="pct_proficient",
    dims=[ColumnPair("region", "region")],
    workbook="DDI Suite",
)
COUNT = Comparison(id="count", measure="count_students", workbook="DDI Suite")


def _cfg(*decisions):
    return ViewConfig(
        view="v",
        fact="m.fct",
        comparisons=[SCHOOL, REGION, COUNT],
        decisions=list(decisions),
    )


def _cause(id, comparison, label, call="deliberate"):
    return Decision(
        id=id,
        comparison=comparison,
        call=call,
        reason="the owner says both are right",
        cause={"side": "dashboard", "label": label},
    )


def test_a_cause_decided_deliberate_drafts_one_line_per_measure():
    cfg = _cfg(
        _cause("d1", "mastery-school", "the dashboard drops WPP modules"),
        # The same cause proven on the region comparison: one line, 2 ids.
        _cause("d2", "mastery-region", "the dashboard drops WPP modules"),
        _cause("d3", "mastery-school", "not this one", call="domain_owner"),
    )

    (note,) = describe.notes(cfg)

    assert note.measure == "pct_proficient" and note.dashboards == ["DDI Suite"]
    assert note.lines == [
        (
            "the dashboard drops WPP modules (dashboard side)",
            "the owner says both are right",
            ["d1", "d2"],
        )
    ]
    assert note.draft() == (
        "Differs from DDI Suite on purpose: the dashboard drops WPP modules "
        "(dashboard side)."
    )


def test_a_missing_filter_reads_under_every_measure_and_values_stay_out():
    cfg = _cfg(
        Decision(
            id="g1",
            comparison="",
            call="deliberate",
            reason="Cube has no school-type member yet",
            missing_filter="School Type",
        ),
        Decision(
            id="r1",
            comparison="count",
            call="deliberate",
            reason="student 1234567 moved mid-year",
            group={"column": "abbreviation", "values": ["Secret School"]},
        ),
    )

    notes = {n.measure: n for n in describe.notes(cfg)}

    assert set(notes) == {"pct_proficient", "count_students"}
    assert notes["pct_proficient"].lines[0][0] == (
        "the dashboard's sheet filter `School Type` has no Cube member"
    )
    text = describe.render([cfg])
    assert "Secret School" not in text and "1234567" not in text
    assert "student <n> moved mid-year" in text


def test_describe_says_so_when_nothing_is_deliberate(tmp_path, capsys):
    path = tmp_path / "v.yml"
    path.write_text("view: v\nfact: m.fct\ncomparisons:\n  - id: c\n    measure: m\n")

    assert cli.main(["describe", str(path)]) == 0

    assert "nothing to describe" in capsys.readouterr().out


def test_a_draft_past_cube_s_cap_says_to_shorten_it():
    long = _cause("d1", "count", "x" * (describe.AI_CONTEXT_CAP + 10))

    assert "Shorten it." in describe.render([_cfg(long)])
