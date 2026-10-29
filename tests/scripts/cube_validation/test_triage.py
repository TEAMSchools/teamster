from datetime import datetime, timezone
from types import SimpleNamespace

from cube_validation import pipeline

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.compare import CellDiff, Gap, Group
from cube_validation.config import ColumnPair, Comparison, Proof, ViewConfig
from cube_validation.cube_client import MemberDoc
from cube_validation.decisions import Applied
from cube_validation.moment import Build
from cube_validation.report import RunResult
from cube_validation.triage import (
    BATCH_CAP,
    REFERENCE_MAX_VALUES,
    SUGGESTIONS,
    Item,
    Suggestion,
    batch_lines,
    open_items,
    pii_members,
    suggest,
    value_check,
)

START = datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc)
END = datetime(2026, 10, 27, 6, 5, tzinfo=timezone.utc)


def _proof(**kw):
    return Proof(fingerprint="f", cells=None, proven_at="2026-10-27", **kw)


def _cfg(**proof_kw):
    cmp = Comparison(
        id="enrollment",
        measure="student_count",
        dims=[ColumnPair("Grade", "grade_level")],
        proof=_proof(**proof_kw),
    )
    return ViewConfig(view="enrollment", fact="d.t", comparisons=[cmp])


def _run(groups=(), gaps=(), cells=()):
    return RunResult(
        view="enrollment",
        moment=Build(start=START, end=END, job_id="j"),
        measures=[],
        applied=Applied(
            open=list(groups), open_gaps=list(gaps), open_cells=list(cells)
        ),
    )


def _gap(field="Enroll Status", kind="filter"):
    return Gap(kind, field, ("Roster",), ("enrollment",), restricting=False)


def _doc(name, description="", ai_context="", title=""):
    return MemberDoc(name, title, description, ai_context, "dimension")


def test_unrestricting_filter_suggests_filters_nothing():
    cfg = _cfg(restricting_filters=[])

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "filters_nothing"
    assert s.evidence == ("keeps every member on Roster",)


def test_copy_note_suggests_filters_nothing():
    cfg = _cfg(
        restricting_filters=["Enroll Status"],
        filter_notes={"Enroll Status": "copy of Grade"},
    )

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "filters_nothing"
    assert s.evidence == ("copy of Grade",)


def test_caption_match_lists_candidates_without_value_check():
    cfg = _cfg(restricting_filters=["Grade Level"])
    docs = {"grade_level": _doc("grade_level"), "region": _doc("region")}

    [s] = suggest(cfg, _run(gaps=[_gap("Grade Level")]), docs)

    assert s.suggestion == "owner"
    assert s.candidates == ("grade_level",)


def test_same_values_suggests_map_filters():
    cfg = _cfg(restricting_filters=["Grade Level"])
    docs = {"grade_level": _doc("grade_level")}
    seen = []

    def values(caption, member):
        seen.append((caption, member))
        return "same values on 9 of 9"

    [s] = suggest(cfg, _run(gaps=[_gap("Grade Level")]), docs, values)

    assert seen == [("Grade Level", "grade_level")]
    assert s.suggestion == "map_filters"
    assert s.candidates == ("grade_level",)
    assert s.evidence == ("grade_level: same values on 9 of 9",)


def test_every_verdict_reaches_the_evidence_but_only_same_maps():
    cfg = _cfg(restricting_filters=["Grade Level"])
    docs = {"grade_level": _doc("grade_level")}

    [s] = suggest(
        cfg,
        _run(gaps=[_gap("Grade Level")]),
        docs,
        lambda c, m: "same field, different coding",
    )

    assert s.suggestion == "owner"
    assert s.candidates == ("grade_level",)
    assert "grade_level: same field, different coding" in s.evidence

    [s] = suggest(
        cfg,
        _run(gaps=[_gap("Grade Level")]),
        docs,
        lambda c, m: "not compared: identifier column",
    )
    assert "grade_level: not compared: identifier column" in s.evidence


def test_member_docs_suggest_docs_with_quoted_evidence():
    cfg = _cfg()
    docs = {
        "student_count": _doc("student_count", description="Counts enrolled students."),
        "grade_level": _doc("grade_level", ai_context="Use for the grade filter."),
    }
    group = Group("enrollment", (("grade_level", "9"),), "value_differs", 40, 38)

    [s] = suggest(cfg, _run(groups=[group]), docs)

    assert s.suggestion == "docs"
    assert s.evidence == (
        "student_count: Counts enrolled students.",
        "grade_level: Use for the grade filter.",
    )


def _measure_doc(description="", ai_context=""):
    return MemberDoc(
        "student_count", "Student Count", description, ai_context, "measure"
    )


def test_group_column_named_in_the_measure_description_suggests_docs():
    docs = {
        "student_count": _measure_doc("Counts students; grade level is as of entry.")
    }
    group = Group("enrollment", (("grade_level", "9"),), "cube_only", 40, 38)

    [s] = suggest(_cfg(), _run(groups=[group]), docs)

    assert s.suggestion == "docs"
    assert s.evidence == (
        "student_count: Counts students; grade level is as of entry.",
    )


def test_group_column_in_no_description_goes_to_owner_with_the_quote():
    # The measure's description always exists; on its own it answers nothing.
    docs = {"student_count": _measure_doc("Counts enrolled students.")}
    group = Group("enrollment", (("grade_level", "9"),), "cube_only", 40, 38)

    [s] = suggest(_cfg(), _run(groups=[group]), docs)

    assert s.suggestion == "owner"
    assert s.evidence == (
        "student_count: Counts enrolled students.",
        "no description or ai_context answers it",
    )


def test_measure_name_tokens_do_not_make_a_description_specific():
    # `student_count` names the measure: its own words never count.
    docs = {"student_count": _measure_doc("Student count per student group.")}
    group = Group("enrollment", (("student_group", "ELL"),), "cube_only", 40, 38)

    [s] = suggest(_cfg(), _run(groups=[group]), docs)

    assert s.suggestion == "docs"
    group = Group("enrollment", (("student_count_band", "low"),), "cube_only", 40, 38)
    [s] = suggest(_cfg(), _run(groups=[group]), docs)
    assert s.suggestion == "owner"


def test_member_title_of_the_group_column_counts():
    docs = {
        "student_count": _measure_doc("Counts students by cohort year."),
        "entry_cohort": _doc("entry_cohort", title="Cohort Year"),
    }
    group = Group("enrollment", (("entry_cohort", "2020"),), "cube_only", 40, 38)

    [s] = suggest(_cfg(), _run(groups=[group]), docs)

    assert s.suggestion == "docs"


def test_gap_caption_in_a_member_ai_context_suggests_docs():
    cfg = _cfg(restricting_filters=["Enroll Status"])
    docs = {
        "student_count": _measure_doc(ai_context="Excludes no-shows by enroll status.")
    }

    [s] = suggest(cfg, _run(gaps=[_gap("Enroll Status")]), docs)

    assert s.suggestion == "docs"
    assert s.evidence == ("student_count: Excludes no-shows by enroll status.",)


def test_gap_caption_in_no_description_goes_to_owner():
    cfg = _cfg(restricting_filters=["Enroll Status"])
    docs = {"student_count": _measure_doc("Counts enrolled students.")}

    [s] = suggest(cfg, _run(gaps=[_gap("Enroll Status")]), docs)

    assert s.suggestion == "owner"


def test_cell_causes_that_a_description_names_suggest_docs():
    docs = {"student_count": _measure_doc("Rounds the region total, not each school.")}
    generic = CellDiff(
        "enrollment",
        {"differs": 3},
        ("3 cells: 1 display unit apart at 0 decimals",),
    )
    clustered = CellDiff(
        "enrollment", {"differs": 3}, ('3 of 3 in cut {"Region": "Camden"}',)
    )

    [s] = suggest(_cfg(), _run(cells=[generic]), docs)
    assert s.suggestion == "owner"
    [s] = suggest(_cfg(), _run(cells=[clustered]), docs)
    assert s.suggestion == "docs"


def test_nothing_found_goes_to_owner_last():
    cfg = _cfg(restricting_filters=["Odd Field"])
    cells = CellDiff("enrollment", {"differs": 3})
    result = suggest(
        cfg, _run(gaps=[_gap("Odd Field"), _gap("Enroll Status")], cells=[cells]), {}
    )

    names = [s.suggestion for s in result]
    assert names == ["filters_nothing", "owner", "owner"]
    assert names == sorted(names, key=SUGGESTIONS.index)
    assert result[-1].evidence == ("no description or ai_context answers it",)
    assert SUGGESTIONS == ("map_filters", "filters_nothing", "docs", "owner")


def test_item_ids_are_stable_and_hold_no_unreviewed_value():
    shown = Group("enrollment", (("grade_level", "9"),), "value_differs", 40, 38)
    small = Group("enrollment", (("grade_level", "9"),), "value_differs", 4, 4)
    ident = Group("enrollment", (("student_number", "123456"),), "cube_only", 40, 38)
    cells = CellDiff("enrollment", {"differs": 3, "cube_only": 12})

    items = open_items(
        _run(
            groups=[shown, small, ident],
            gaps=[_gap("Enroll Status"), _gap("Grade", "cut")],
            cells=[cells],
        )
    )

    by_id = {i.id: i for i in items}
    assert "enrollment:grade_level=9" in by_id
    assert "enrollment:student_number=<redacted>" in by_id
    assert "enrollment:cells" in by_id
    assert "filter:Enroll Status" in by_id
    assert "cut:Grade" in by_id
    # The id and label hide it; the stub is decision YAML and needs the value.
    assert not any("123456" in i.id + i.label for i in items)
    assert by_id["enrollment:student_number=<redacted>"].stub["group"] == {
        "column": "student_number",
        "values": ["123456"],
    }
    # A group under 10 students never shows its value.
    small_item = items[1]
    assert small_item.id == "enrollment:grade_level=<redacted>"
    assert small_item.stub["group"]["values"] == ["9"]
    assert "<10 rows" in small_item.label and "<10 students" in small_item.label
    assert by_id["enrollment:grade_level=9"].stub == {
        "comparison": "enrollment",
        "group": {"column": "grade_level", "values": ["9"]},
    }
    assert by_id["enrollment:cells"].stub == {
        "comparison": "enrollment",
        "cells": True,
    }
    assert by_id["cut:Grade"].stub == {"missing_cut": "Grade"}
    assert by_id["filter:Enroll Status"].stub == {"missing_filter": "Enroll Status"}
    assert open_items(_run(groups=[shown])) == open_items(_run(groups=[shown]))


def test_colliding_masked_ids_get_a_stable_suffix():
    a = Group("enrollment", (("student_number", "222"),), "cube_only", 2, 2)
    b = Group("enrollment", (("student_number", "111"),), "cube_only", 2, 2)

    items = open_items(_run(groups=[a, b]))
    flipped = open_items(_run(groups=[b, a]))

    # The raw dims order the suffix, so the input order does not matter.
    assert [i.id for i in items] == [
        "enrollment:student_number=<redacted>#2",
        "enrollment:student_number=<redacted>",
    ]
    assert {i.id: i.stub["group"]["values"] for i in items} == {
        i.id: i.stub["group"]["values"] for i in flipped
    }
    assert {i.id: i.stub["group"]["values"] for i in items}[
        "enrollment:student_number=<redacted>"
    ] == ["111"]


def test_colliding_ids_keep_their_own_docs_evidence():
    cfg = _cfg()
    docs = {
        "student_number": _doc("student_number", description="The student's number.")
    }
    a = Group("enrollment", (("student_number", "222"),), "cube_only", 2, 2)
    b = Group("enrollment", (("grade_level", "9"),), "value_differs", 2, 2)
    c = Group("enrollment", (("grade_level", "9"),), "cube_only", 40, 38)

    result = suggest(cfg, _run(groups=[a, b, c]), docs)

    by_id = {s.item.id: s for s in result}
    assert by_id["enrollment:student_number=<redacted>"].suggestion == "docs"
    assert by_id["enrollment:grade_level=<redacted>"].suggestion == "owner"
    assert by_id["enrollment:grade_level=9"].suggestion == "owner"


def test_stub_takes_the_first_column_no_sibling_shares():
    one = Group(
        "enrollment",
        (("region", "Newark"), ("grade_level", "9")),
        "value_differs",
        40,
        38,
    )
    two = Group(
        "enrollment",
        (("region", "Newark"), ("grade_level", "10")),
        "value_differs",
        40,
        38,
    )

    items = open_items(_run(groups=[one, two]))

    assert [i.stub["group"] for i in items] == [
        {"column": "grade_level", "values": ["9"]},
        {"column": "grade_level", "values": ["10"]},
    ]
    result = suggest(_cfg(), _run(groups=[one, two]), {})
    assert not any("also covers" in e for s in result for e in s.evidence)


def test_stub_with_no_unique_column_names_what_it_also_covers():
    one = Group("enrollment", (("region", "Newark"),), "value_differs", 40, 38)
    two = Group("enrollment", (("region", "Newark"),), "cube_only", 40, 38)

    result = suggest(_cfg(), _run(groups=[one, two]), {})

    assert [i.stub["group"]["column"] for i in open_items(_run(groups=[one, two]))] == [
        "region",
        "region",
    ]
    # The suffix follows the sort on raw dims then bucket, so `cube_only` is
    # first and the first-listed `value_differs` group is the `#2`.
    by_id = {s.item.id: s for s in result}
    assert by_id["enrollment:region=Newark#2"].evidence[-1] == (
        "also covers: enrollment:region=Newark"
    )
    assert by_id["enrollment:region=Newark"].evidence[-1] == (
        "also covers: enrollment:region=Newark#2"
    )


def test_no_group_by_stub_matches_a_row_with_no_group_by():
    whole = Group("enrollment", (), "value_differs", 40, 38)

    [item] = open_items(_run(groups=[whole]))

    assert item.stub["group"] == {"column": "", "values": [""]}


def test_unknown_proof_on_the_gap_sheet_is_not_filters_nothing():
    known = Comparison(id="other", measure="m", proof=_proof(restricting_filters=[]))
    unknown = Comparison(id="enrollment", measure="m", proof=_proof())
    cfg = ViewConfig(view="enrollment", fact="d.t", comparisons=[known, unknown])

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "owner"


def test_another_sheets_note_does_not_speak_for_the_gap():
    other = Comparison(
        id="other",
        measure="m",
        proof=_proof(
            restricting_filters=[], filter_notes={"Enroll Status": "copy of X"}
        ),
    )
    mine = Comparison(
        id="enrollment",
        measure="m",
        proof=_proof(restricting_filters=["Enroll Status"]),
    )
    cfg = ViewConfig(view="enrollment", fact="d.t", comparisons=[other, mine])

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "owner"


# --- value_check -------------------------------------------------------------


class _Wh:
    def __init__(self, values):
        self.values, self.ran = values, []

    def rows(self, sql):
        self.ran.append(sql)
        return [{"value": v} for v in self.values]


def _check(
    monkeypatch,
    dash,
    theirs,
    member="school_level",
    pii=frozenset(),
    column="school_level",
):
    """Run `value_check` against fake warehouse and Cube value sets."""
    wh = _Wh(dash)
    loads = []

    def load(cube, wh_, query):
        loads.append(query)
        return [{f"enrollment.{member}": v} for v in theirs]

    monkeypatch.setattr(
        pipeline, "_as_of", lambda sql, ts, wh_: SimpleNamespace(sql=sql)
    )
    monkeypatch.setattr(pipeline, "_priced_load", load)
    cfg = _cfg(missing_columns={"School Level": column})
    object.__setattr__(cfg.comparisons[0], "dashboard_view", "ds.rpt_d")
    verdict = value_check(
        wh, object(), cfg, column, member, Build(START, END, "j"), set(pii)
    )
    return verdict, wh, loads


def test_value_check_skips_identifier_and_high_cardinality_columns(monkeypatch, capsys):
    verdict, wh, loads = _check(monkeypatch, ["1"], ["1"], member="student_number")
    assert verdict == "not compared: identifier column"
    assert wh.ran == [] and loads == []

    verdict, wh, loads = _check(monkeypatch, ["1"], ["1"], member="x", pii={"x"})
    assert verdict == "not compared: identifier column"
    assert wh.ran == [] and loads == []

    many = [f"v{i}" for i in range(REFERENCE_MAX_VALUES + 1)]
    verdict, _, _ = _check(monkeypatch, many, many)
    assert verdict == "not compared: identifier column"
    verdict, _, _ = _check(monkeypatch, ["a"], many)
    assert verdict == "not compared: identifier column"
    assert "v0" not in capsys.readouterr().out


def test_value_check_same_values_and_different_coding(monkeypatch, capsys):
    verdict, wh, loads = _check(monkeypatch, ["A", "B"], ["B", "A"])
    assert verdict == "same values: map it under filters:"
    assert "`ds`.`rpt_d`" in wh.ran[0]
    assert loads[0]["dimensions"] == ["enrollment.school_level"]

    verdict, _, _ = _check(monkeypatch, ["W", "B"], ["White", "Black"])
    assert verdict == "same field, different coding"

    # Every candidate already matched by name or description, so a difference
    # in values is a difference in coding.
    verdict, _, _ = _check(monkeypatch, ["1", "2"], ["White", "Black"])
    assert verdict == "same field, different coding"
    # An unreviewed member's values never print.
    assert "White" not in capsys.readouterr().out


def test_value_check_prints_values_only_for_a_shown_column(monkeypatch, capsys):
    verdict, _, _ = _check(
        monkeypatch, ["Sr"], ["Jr"], member="grade_level", column="grade_level"
    )
    assert verdict == "same field, different coding"
    assert "Sr" in capsys.readouterr().out


def test_value_check_prints_nothing_when_the_column_is_not_shown(monkeypatch, capsys):
    verdict, _, _ = _check(
        monkeypatch, ["Sr"], ["Jr"], member="grade_level", column="school_level"
    )
    assert verdict == "same field, different coding"
    assert "Sr" not in capsys.readouterr().out


def test_value_check_runs_no_query_for_an_identifier_column(monkeypatch):
    for column in ("student_number", "x_id", "full_name", "contact_email"):
        verdict, wh, loads = _check(monkeypatch, ["1"], ["1"], column=column)
        assert verdict == "not compared: identifier column"
        assert wh.ran == [] and loads == []


def test_value_check_counts_rows_before_dropping_nulls(monkeypatch):
    # A null plus 50 real values fills the limit: the set may be cut short.
    cut = [f"v{i}" for i in range(REFERENCE_MAX_VALUES)] + [None]
    verdict, _, _ = _check(monkeypatch, ["a"], cut)
    assert verdict == "not compared: identifier column"


def test_value_check_reads_the_dashboard_as_of_the_run_start(monkeypatch):
    seen = []
    monkeypatch.setattr(
        pipeline,
        "_as_of",
        lambda sql, ts, wh: seen.append(ts) or SimpleNamespace(sql=sql),
    )
    monkeypatch.setattr(pipeline, "_priced_load", lambda c, w, q: [])
    cfg = _cfg()
    object.__setattr__(cfg.comparisons[0], "dashboard_view", "ds.rpt_d")
    value_check(_Wh(["a"]), object(), cfg, "col", "m", Build(START, END, "j"), set())
    assert seen == [START]


def _suggestion(n, call, kind="group", comparison="enrollment"):
    item = Item(f"{comparison}:{n}", kind, comparison, f"label {n}", {})
    return Suggestion(item, call, (f"evidence {n}",))


def test_batch_starts_with_a_summary_per_comparison():
    cube_only = Group("enrollment", (("grade_level", "9"),), "cube_only", 40, 38)
    dash_only = Group("enrollment", (("grade_level", "10"),), "dashboard_only", 40, 38)
    run = _run(groups=[cube_only, dash_only], gaps=[_gap()])
    found = suggest(_cfg(restricting_filters=[]), run, {})

    lines = batch_lines(run, found)

    summary = lines[: lines.index("")]
    assert summary == [
        "Summary",
        "  enrollment: 3 items",
        "    by suggestion: filters_nothing 1, owner 2",
        "    by kind: gap 1, group 2",
        "    groups by bucket: cube_only 1, dashboard_only 1",
    ]
    assert "filters_nothing (1)" in lines and "owner (2)" in lines


def test_batch_lists_at_most_the_cap_per_suggestion():
    found = [_suggestion(n, "owner") for n in range(BATCH_CAP + 5)]
    found += [_suggestion("d", "docs")]

    lines = batch_lines(_run(), found)

    assert BATCH_CAP == 25
    assert f"owner ({BATCH_CAP + 5})" in lines
    assert sum(line.startswith("- label ") for line in lines) == BATCH_CAP + 1
    assert "- label 24" in lines and "- label 25" not in lines
    assert "  … 5 more in triage.json" in lines
    assert not any(
        "more in triage.json" in line for line in lines[: lines.index("owner (30)")]
    )


def test_pii_members_reads_contains_pii_from_meta():
    meta = {
        "cubes": [
            {
                "name": "enrollment",
                "dimensions": [
                    {"name": "enrollment.ssn", "meta": {"contains_pii": True}},
                    {"name": "enrollment.region", "meta": {}},
                ],
            },
            {
                "name": "other",
                "dimensions": [{"name": "other.x", "meta": {"contains_pii": True}}],
            },
        ]
    }
    assert pii_members(meta, "enrollment") == {"ssn"}
