from datetime import datetime, timezone
from types import SimpleNamespace

from cube_validation import explain, pipeline, trace
from cube_validation.config import ColumnPair, Comparison, RebuildCheck, ViewConfig
from cube_validation.cube_client import MemberDoc
from cube_validation.decisions import Applied
from cube_validation.moment import Build

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.reconcile import CellDiff, Gap, Group
from cube_validation.report import RunResult
from cube_validation.sort import (
    BATCH_CAP,
    NO_GRAIN,
    NO_ROWS,
    NOT_TRACED,
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


def _rebuild_check(**kw):
    return RebuildCheck(fingerprint="f", cells=None, matched_at="2026-10-27", **kw)


def _cfg(**check_kw):
    cmp = Comparison(
        id="enrollment",
        measure="student_count",
        dims=[ColumnPair("Grade", "grade_level")],
        rebuild_check=_rebuild_check(**check_kw),
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


def _doc(name, description="", title=""):
    return MemberDoc(name, title, description, "dimension")


def test_unrestricting_filter_suggests_filters_nothing():
    cfg = _cfg(restricting_filters=[])

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "filters_nothing"
    assert s.evidence == (
        "Workbook-only field: no datasource column behind it",
        "keeps every member on Roster",
    )


def test_copy_note_suggests_filters_nothing():
    cfg = _cfg(
        restricting_filters=["Enroll Status"],
        filter_notes={"Enroll Status": "copy of Grade"},
    )

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "filters_nothing"
    assert s.evidence == (
        "Workbook-only field: no datasource column behind it",
        "copy of Grade",
    )


def test_caption_match_lists_candidates_without_value_check():
    cfg = _cfg(restricting_filters=["Grade Level"])
    docs = {"grade_level": _doc("grade_level"), "region": _doc("region")}

    [s] = suggest(cfg, _run(gaps=[_gap("Grade Level")]), docs)

    # The sheet carries the filter: that explains it; the owner decides on it.
    assert s.suggestion == "cause"
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
    assert s.evidence == (
        "Cube offers it as `grade_level`, unmapped: "
        "check before mapping it under `filters:`",
        "grade_level: same values on 9 of 9",
    )


def test_every_verdict_reaches_the_evidence_but_only_same_maps():
    cfg = _cfg(restricting_filters=["Grade Level"])
    docs = {"grade_level": _doc("grade_level")}

    [s] = suggest(
        cfg,
        _run(gaps=[_gap("Grade Level")]),
        docs,
        lambda c, m: "same field, different coding",
    )

    assert s.suggestion == "cause"
    assert s.candidates == ("grade_level",)
    assert "grade_level: same field, different coding" in s.evidence

    [s] = suggest(
        cfg,
        _run(gaps=[_gap("Grade Level")]),
        docs,
        lambda c, m: "not compared: identifier column",
    )
    assert "grade_level: not compared: identifier column" in s.evidence


def _measure_doc(description=""):
    return MemberDoc("student_count", "Student Count", description, "measure")


def test_an_item_no_filter_evidence_answers_goes_to_investigate():
    group = Group("enrollment", (("grade_level", "9"),), "cube_only", 40, 38)

    [s] = suggest(_cfg(), _run(groups=[group]), {})

    assert s.suggestion == "investigate"
    assert s.cause is None
    assert s.evidence == (NOT_TRACED,)


def test_member_docs_are_never_evidence_on_a_group_or_cell_set():
    # A description naming the group's column has never explained a missing
    # row; the comparison's model doc is the lead instead.
    docs = {
        "student_count": _measure_doc("Counts students; grade level is as of entry."),
        "grade_level": _doc("grade_level", "Use for the grade filter."),
    }
    group = Group("enrollment", (("grade_level", "9"),), "cube_only", 40, 38)
    cfg = _cfg(restricting_filters=["Enroll Status"])
    gap_docs = {"student_count": _measure_doc("Excludes enroll status X.")}
    lead = {"enrollment": "lead: read docs/models/x.md (mentions rpt_x)"}

    [s] = suggest(cfg, _run(groups=[group]), docs, leads=lead)
    [gap] = suggest(cfg, _run(gaps=[_gap("Enroll Status")]), gap_docs, leads=lead)
    [cells] = suggest(
        cfg, _run(cells=[CellDiff("enrollment", {"differs": 3})]), docs, leads=lead
    )

    assert s.suggestion == cells.suggestion == "investigate"
    assert gap.suggestion == "cause"
    assert s.evidence == (NOT_TRACED, lead["enrollment"])
    assert cells.evidence == (lead["enrollment"],)
    assert gap.evidence == (
        "Workbook-only field: no datasource column behind it",
        "Roster carries it; Cube has no member for it",
    )


def test_piles_sort_in_batch_order_investigate_last():
    cfg = _cfg(restricting_filters=["Odd Field"])
    cells = CellDiff("enrollment", {"differs": 3})
    result = suggest(
        cfg, _run(gaps=[_gap("Odd Field"), _gap("Enroll Status")], cells=[cells]), {}
    )

    names = [s.suggestion for s in result]
    assert names == ["filters_nothing", "cause", "investigate"]
    assert names == sorted(names, key=SUGGESTIONS.index)
    assert SUGGESTIONS == ("map_filters", "filters_nothing", "cause", "investigate")


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
    # Its label stays local, so it shows exact counts.
    assert ": 4 rows, 4 students" in small_item.label
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


def test_no_group_by_stub_matches_a_row_with_no_group_by():
    whole = Group("enrollment", (), "value_differs", 40, 38)

    [item] = open_items(_run(groups=[whole]))

    assert item.stub["group"] == {"column": "", "values": [""]}


def test_unknown_rebuild_check_on_the_gap_sheet_is_not_filters_nothing():
    known = Comparison(
        id="other", measure="m", rebuild_check=_rebuild_check(restricting_filters=[])
    )
    unknown = Comparison(id="enrollment", measure="m", rebuild_check=_rebuild_check())
    cfg = ViewConfig(view="enrollment", fact="d.t", comparisons=[known, unknown])

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "cause"


def test_another_sheets_note_does_not_speak_for_the_gap():
    other = Comparison(
        id="other",
        measure="m",
        rebuild_check=_rebuild_check(
            restricting_filters=[], filter_notes={"Enroll Status": "copy of X"}
        ),
    )
    mine = Comparison(
        id="enrollment",
        measure="m",
        rebuild_check=_rebuild_check(restricting_filters=["Enroll Status"]),
    )
    cfg = ViewConfig(view="enrollment", fact="d.t", comparisons=[other, mine])

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "cause"


# --- the trace and the gap ruling --------------------------------------------


def test_a_gap_the_sheet_carries_is_an_explained_dashboard_step():
    cfg = _cfg(restricting_filters=["Enroll Status"])

    [cut] = suggest(cfg, _run(gaps=[_gap("Week", "cut")]), {})
    [flt] = suggest(cfg, _run(gaps=[_gap("Enroll Status")]), {})

    assert cut.suggestion == flt.suggestion == "cause"
    assert cut.cause == [
        {"side": "dashboard", "step": "sheet cut Week", "label": "sheet cut Week",
         "n_rows": None}
    ]  # fmt: skip
    assert flt.cause[0]["step"] == "sheet filter Enroll Status"


def test_a_gap_that_maps_or_filters_nothing_keeps_its_pile():
    cfg = _cfg(restricting_filters=[])

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "filters_nothing" and s.cause is None


def _traced(n_rows, **steps):
    t = trace.ItemTrace("dashboard", n_rows)
    for i, (label, n) in enumerate(steps.items()):
        t.steps[f"dashboard:responses:{i}"] = n
        t.labels[f"dashboard:responses:{i}"] = label
    return t


def test_the_trace_never_yields_cause():
    group = Group("enrollment", (("grade_level", "9"),), "cube_only", 40, 38)
    traces = {trace.item_key(group): _traced(40, wpp=30, week_end=10)}

    [s] = suggest(_cfg(), _run(groups=[group]), {}, traces=traces)

    assert s.suggestion == "investigate" and s.cause is None
    assert s.evidence[:2] == (
        "lead: relaxing wpp brings back 30 of 40 rows",
        "lead: relaxing week_end brings back 10 of 40 rows",
    )


def test_a_lead_is_exact_locally_and_masked_for_the_review_issue():
    group = Group("enrollment", (("grade_level", "9"),), "dashboard_only", 40, 38)
    traces = {trace.item_key(group): _traced(40, wpp=35, week_end=5)}

    [s] = suggest(_cfg(), _run(groups=[group]), {}, traces=traces)

    assert s.evidence[:2] == (
        "lead: relaxing wpp brings back 35 of 40 rows",
        "lead: relaxing week_end brings back 5 of 40 rows",
    )
    assert s.posted[:2] == (
        # Beside a hidden part the total is a bound, never exact.
        "lead: relaxing wpp brings back masked of 10+ rows",
        "lead: relaxing week_end brings back <10 of 10+ rows",
    )


def test_rows_the_sheet_s_own_filter_drops_are_a_cause_with_no_trace():
    cfg = _cfg()
    cfg.comparisons[0].dashboard_filters.append(
        {"dashboard": "administered_at", "operator": "lte", "days_from_week_end": 0}
    )
    group = Group(
        "enrollment",
        (("dashboard_filter", "administered_at"), ("grade_level", "9")),
        "dashboard_filtered",
        12,
        9,
    )

    # `--no-trace`: the reconcile alone explains it.
    [s] = suggest(cfg, _run(groups=[group]), {}, traces=None)

    assert s.suggestion == "cause" and s.explanation["kind"] == "reconcile"
    assert s.explanation["fingerprint"]
    assert s.cause[0]["n_rows"] == 12
    assert s.cause[0]["label"] == "sheet filter administered_at"
    assert "(administered_at <= " in s.evidence[0]
    assert s.evidence[0].endswith("drops all 12 rows")
    assert s.posted[0].endswith("drops every row")
    # Decided on its cause, never by a column value.
    assert "group" not in s.item.stub


def test_a_gap_the_workbook_carries_rests_on_the_workbook():
    [s] = suggest(_cfg(), _run(gaps=[_gap("Team", "cut")]), {})

    assert s.suggestion == "cause" and s.explanation == {"kind": "workbook"}


def test_a_group_with_an_unattributed_row_stays_in_investigate():
    group = Group("enrollment", (("grade_level", "9"),), "cube_only", 40, 38)
    found = _traced(40, wpp=39)
    found.none = 1
    docs = {"student_count": _measure_doc("Counts students.")}

    [s] = suggest(
        _cfg(), _run(groups=[group]), docs, traces={trace.item_key(group): found}
    )

    assert s.suggestion == "investigate" and s.cause is None
    # 1 of 40 masked alone would read as 40 - 39: the 39 hides too, and the
    # total then gives only their sum.
    assert s.evidence == (
        "lead: relaxing wpp brings back 39 of 40 rows",
        "1 rows unattributed: 1 recovered by no step",
    )
    assert ": 40 rows, " in s.item.label


def test_groups_the_trace_cannot_reach_say_why():
    differs = Group("enrollment", (("grade_level", "9"),), "value_differs", 40, 38)
    one_sided = Group("enrollment", (("grade_level", "10"),), "cube_only", 40, 38)

    found = suggest(_cfg(), _run(groups=[differs, one_sided]), {}, traces={})

    assert [s.evidence[0] for s in found] == [NO_ROWS, NO_GRAIN]
    assert {s.suggestion for s in found} == {"investigate"}


def test_cell_sets_stay_in_investigate_whatever_the_trace_found():
    cells = CellDiff("enrollment", {"differs": 3})

    [s] = suggest(_cfg(), _run(cells=[cells]), {}, traces={})

    assert s.suggestion == "investigate"


def _formula_run(n=3):
    cells = CellDiff("enrollment", {"differs": 2})
    formula = CellDiff("enrollment", {"differs": n}, kind="formula")
    run = _run(cells=[cells, formula])
    run.fingerprints = {"enrollment": {"cube": "c1", "dashboard": "d1"}}
    return run


def test_a_formula_difference_is_its_own_item():
    by_id = {i.id: i for i in open_items(_formula_run())}

    formula = by_id["enrollment:formula"]
    assert formula.kind == "formula" and formula.comparison == "enrollment"
    assert formula.stub == {"comparison": "enrollment", "formula": True}
    assert by_id["enrollment:cells"].kind == "cells"


def test_a_formula_difference_is_in_cause_on_the_run_s_own_evidence():
    import hashlib

    from cube_validation.sort import EXPLANATION_KINDS

    found = {s.item.id: s for s in suggest(_cfg(), _formula_run(), {}, traces={})}

    s = found["enrollment:formula"]
    assert s.suggestion == "cause"
    assert s.cause == [{"side": "both", "step": "formula",
                        "label": "differing cells hold no unmatched row",
                        "n_rows": None}]  # fmt: skip
    fp = json.dumps({"cube": "c1", "dashboard": "d1"}, sort_keys=True)
    assert s.explanation == {
        "kind": "formula",
        "fingerprint": hashlib.sha256(fp.encode()).hexdigest(),
    }
    assert "formula" in EXPLANATION_KINDS
    words = (
        "differing cells hold no unmatched row: every row in them matched on both sides"
    )
    assert s.evidence == (f"3 {words}",)
    # Posted to GitHub: the count is masked.
    assert s.posted == (f"<10 {words}",)
    assert found["enrollment:cells"].suggestion == "investigate"
    big = {s.item.id: s for s in suggest(_cfg(), _formula_run(12), {}, traces={})}
    assert big["enrollment:formula"].posted == (f"12 {words}",)


def _matched_run(n, matched_only):
    """`_formula_run` whose formula difference holds `matched_only` cells the
    formula check filed, each saved in `diff_cells`."""
    from dataclasses import replace

    run = _formula_run(n)
    cells, formula = run.applied.open_cells
    run.applied.open_cells = [cells, replace(formula, matched_only=matched_only)]
    run.diff_cells = [
        {"comparison": "enrollment", "cut": "{}", "key": f"Grade={g}",
         "dims": [["Grade", str(g)]], "dashboard": 0.6, "cube": 0.5,
         "n_students": None, "kind": "formula"}
        for g in range(9, 9 + n)
    ]  # fmt: skip
    return run


def test_formula_evidence_counts_matched_row_cells_masked():
    # trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
    from cube_validation.sort import FORMULA_LABEL, MATCHED_LABEL

    def formula_item(run):
        found = {s.item.id: s for s in suggest(_cfg(), run, {}, traces={})}
        return found["enrollment:formula"]

    s = formula_item(_matched_run(3, 3))

    assert MATCHED_LABEL == "differing cells differ on matched rows"
    assert s.suggestion == "cause"
    assert [c["label"] for c in s.cause] == [MATCHED_LABEL]
    assert s.evidence[0].startswith(f"3 {MATCHED_LABEL}: ")
    assert s.posted == (f"<10 {s.evidence[0][2:]}",)
    # A cell's dims are local evidence only.
    local = " ".join(s.evidence)
    assert all(f"Grade={g}" in local for g in (9, 10, 11))
    assert "Grade=" not in " ".join(s.posted)

    # One line per origin, each count masked when posted.
    both = formula_item(_matched_run(12, 3))
    assert both.evidence[0] == (
        f"9 {FORMULA_LABEL}: every row in them matched on both sides"
    )
    assert both.evidence[1].startswith(f"3 {MATCHED_LABEL}: ")
    assert [p.split(" ", 1)[0] for p in both.posted] == ["<10", "<10"]

    # A run with no formula check sorts as before.
    plain = formula_item(_formula_run())
    assert [c["label"] for c in plain.cause] == [FORMULA_LABEL]
    assert plain.evidence == (
        f"3 {FORMULA_LABEL}: every row in them matched on both sides",
    )


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
        pipeline, "checked_as_of", lambda sql, ts, wh_: SimpleNamespace(sql=sql)
    )
    monkeypatch.setattr(pipeline, "priced_load", load)
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
        "checked_as_of",
        lambda sql, ts, wh: seen.append(ts) or SimpleNamespace(sql=sql),
    )
    monkeypatch.setattr(pipeline, "priced_load", lambda c, w, q: [])
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
        "    by suggestion: filters_nothing 1, investigate 2",
        "    by kind: gap 1, group 2",
        "    groups by bucket: cube_only 1, dashboard_only 1",
    ]
    assert "filters_nothing (1)" in lines and "investigate (2)" in lines


def test_batch_summary_orders_suggestions_as_the_batch_does():
    found = [
        _suggestion("a", "investigate"),
        _suggestion("b", "map_filters", "gap"),
        _suggestion("c", "filters_nothing", "gap"),
    ]

    lines = batch_lines(_run(), found)

    assert "    by suggestion: map_filters 1, filters_nothing 1, investigate 1" in lines


def test_batch_lists_at_most_the_cap_per_suggestion():
    found = [_suggestion(n, "investigate") for n in range(BATCH_CAP + 5)]
    found += [_suggestion("d", "cause")]

    lines = batch_lines(_run(), found)

    assert BATCH_CAP == 25
    assert f"investigate ({BATCH_CAP + 5})" in lines
    assert sum(line.startswith("- label ") for line in lines) == BATCH_CAP + 1
    assert "- label 24" in lines and "- label 25" not in lines
    assert "  … 5 more in sort.json" in lines
    assert not any(
        "more in sort.json" in line for line in lines[: lines.index("investigate (30)")]
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


def test_open_key_changes_when_a_group_or_cell_set_changes_its_counts():
    from cube_validation.sort import _open_key

    dims = (("grade_level", "9"),)
    base = Group("enrollment", dims, "cube_only", 40, 38)
    assert _open_key(base) == _open_key(Group("enrollment", dims, "cube_only", 40, 38))
    assert _open_key(base) != _open_key(Group("enrollment", dims, "cube_only", 41, 38))
    assert _open_key(base) != _open_key(Group("enrollment", dims, "cube_only", 40, 39))

    cells = CellDiff("enrollment", {"differs": 3})
    assert _open_key(cells) != _open_key(CellDiff("enrollment", {"differs": 4}))
    assert _open_key(cells) == _open_key(
        CellDiff("enrollment", {"differs": 3}, ("why",))
    )
    # A formula difference is another item than the cell set it split from.
    assert _open_key(cells) != _open_key(
        CellDiff("enrollment", {"differs": 3}, kind="formula")
    )


# --- cause decisions: what the latest sort says they decide (T17) ----------

import copy  # noqa: E402
import json  # noqa: E402

import pytest  # noqa: E402

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import Decision  # noqa: E402
from cube_validation.sort import (  # noqa: E402
    POSTED_VERSION,
    _moment,
    cause_asks,
    checked_sort,
    mark_decided,
    open_keys,
)

FPS = {"cube": "c1", "dashboard": "d1"}
NO_SECTION = "score has no section"
LATE = "score dated after the week"


def _groups(*schools, n_rows=30, n_students=12, bucket="dashboard_only"):
    return [
        Group("enrollment", (("region", s),), bucket, n_rows, n_students)
        for s in schools
    ]


def _fp_run(groups):
    run = _run(groups=groups)
    run.fingerprints = {"enrollment": dict(FPS)}
    return run


def _explanation_file(tmp_path, text="SELECT 1"):
    path = tmp_path / "enrollment__dashboard_only.sql"
    path.write_text(text)
    return {"kind": "query", "path": str(path),
            "fingerprint": explain.file_fingerprint(path)}  # fmt: skip


def _item(it, explanation, *causes):
    return {"id": it.id, "key": it.key, "kind": "group", "comparison": "enrollment",
            "label": "l", "stub": {"comparison": "enrollment",
                                   "group": {"column": "region", "values": ["x"]}},
            "suggestion": "cause", "evidence": ["proof line"],
            "evidence_posted": ["proof line"], "candidates": [],
            "cause": [{"side": side, "step": "b", "label": label, "n_rows": n}
                      for side, label, n in causes],
            "explanation": explanation, "default_call": ""}  # fmt: skip


def _cause_decision(
    id, label, side="cube", call="domain_owner", explanation=None, **kw
):
    return Decision(id, "enrollment", call, "r",
                    cause={"side": side, "label": label},
                    fingerprints={**FPS, "explanation": explanation or "", **kw.pop("fps", {})},
                    **kw)  # fmt: skip


def test_a_split_group_stays_undecided_until_both_causes_are_decided(tmp_path):
    run = _fp_run(_groups("Newark"))
    (key,) = open_items(run)
    explanation = _explanation_file(tmp_path)
    item = _item(key, explanation, ("cube", NO_SECTION, 20), ("dashboard", LATE, 10))
    a = _cause_decision("a", NO_SECTION, explanation=explanation["fingerprint"])
    b = _cause_decision(
        "b", LATE, side="dashboard", explanation=explanation["fingerprint"]
    )

    half, both = copy.deepcopy(item), copy.deepcopy(item)
    mark_decided(run, [half], [a])
    mark_decided(run, [both], [a, b])

    assert half["decided"] is False
    assert half["decisions"] == {f"cube: {NO_SECTION}": "a", f"dashboard: {LATE}": None}
    assert both["decided"] is True


def test_a_cells_item_is_decided_once_every_covering_group_is(tmp_path):
    run = _fp_run(_groups("Newark", "Miami"))
    newark, miami = open_items(run)
    explanation = _explanation_file(tmp_path)
    groups = [_item(newark, explanation, ("cube", NO_SECTION, 30)),
              _item(miami, explanation, ("dashboard", LATE, 30))]  # fmt: skip
    cells = {"id": "enrollment:cells", "kind": "cells", "comparison": "enrollment",
             "suggestion": "cause", "cause": groups[0]["cause"],
             "explanation": {"kind": "cells", "groups": [newark.id, miami.id],
                       "closed": ["0123456789abcdef"]}}  # fmt: skip
    a = _cause_decision("a", NO_SECTION, explanation=explanation["fingerprint"])
    b = _cause_decision(
        "b", LATE, side="dashboard", explanation=explanation["fingerprint"]
    )

    # The cell set comes first: it is marked after the groups it rests on.
    half = copy.deepcopy([cells, *groups])
    both = copy.deepcopy([cells, *groups])
    mark_decided(run, half, [a])
    mark_decided(run, both, [a, b])

    assert half[0]["decided"] is False
    assert both[0]["decided"] is True
    # A cell set whose covering groups are all closed is decided by their
    # `group` decisions.
    closed_only = copy.deepcopy(cells)
    closed_only["explanation"]["groups"] = []
    mark_decided(run, [closed_only], [])
    assert closed_only["decided"] is True


def test_a_changed_explanation_file_re_opens_the_decision(tmp_path):
    run = _fp_run(_groups("Newark"))
    (key,) = open_items(run)
    old = _explanation_file(tmp_path, "SELECT 1")
    new = _explanation_file(tmp_path, "SELECT 2")
    decision = _cause_decision("a", NO_SECTION, explanation=old["fingerprint"])
    item = _item(key, new, ("cube", NO_SECTION, 30))

    mark_decided(run, [item], [decision], note=True)

    assert item["decided"] is False and item["decisions"] == {
        f"cube: {NO_SECTION}": None
    }
    assert item["evidence"][0] == (
        "decision a: the explanation changed since the decision; re-approve"
    )


def test_a_cause_decision_on_other_sql_does_not_decide(tmp_path):
    run = _fp_run(_groups("Newark"))
    (key,) = open_items(run)
    explanation = _explanation_file(tmp_path)
    stale = _cause_decision("a", NO_SECTION, explanation=explanation["fingerprint"],
                            fps={"cube": "old"})  # fmt: skip
    item = _item(key, explanation, ("cube", NO_SECTION, 30))

    mark_decided(run, [item], [stale], note=True)

    assert item["decided"] is False
    assert "SQL changed since the decision" in item["evidence"][0]


def _group_decision(call, fps=FPS):
    return Decision("by-region", "enrollment", call, "r",
                    group={"column": "region", "values": ["Newark"]},
                    fingerprints=dict(fps))  # fmt: skip


def test_a_cause_decision_agreeing_with_a_group_decision_is_redundant(tmp_path):
    run = _fp_run(_groups("Newark"))
    (key,) = open_items(run)
    explanation = _explanation_file(tmp_path)
    item = _item(key, explanation, ("cube", NO_SECTION, 30))
    cause = _cause_decision(
        "a", NO_SECTION, call="fix_cube", explanation=explanation["fingerprint"]
    )

    mark_decided(run, [item], [_group_decision("fix_cube"), cause], note=True)

    assert item["evidence"][0] == "decision a repeats group decision by-region"


@pytest.mark.parametrize("fps", [FPS, {"cube": "stale", "dashboard": "stale"}])
def test_a_cause_decision_disagreeing_with_a_group_decision_refuses(tmp_path, fps):
    run = _fp_run(_groups("Newark"))
    (key,) = open_items(run)
    explanation = _explanation_file(tmp_path)
    item = _item(key, explanation, ("cube", NO_SECTION, 30))
    cause = _cause_decision("a", NO_SECTION, explanation=explanation["fingerprint"])

    # Refused even while the group decision waits to be re-confirmed.
    with pytest.raises(
        pipeline.Refusal, match=r"'by-region' \(fix_cube\).*'a'.*disagree"
    ):
        mark_decided(
            run, [item], [_group_decision("fix_cube", fps), cause], refuse=True
        )


def test_cause_asks_count_only_each_causes_own_rows(tmp_path):
    run = _fp_run(_groups("Newark", "Camden"))
    newark, camden = open_items(run)
    explanation = _explanation_file(tmp_path)
    fp = explanation["fingerprint"]
    items = [
        _item(newark, explanation, ("cube", NO_SECTION, 27), ("cube", LATE, 3)),
        _item(camden, explanation, ("cube", NO_SECTION, 30)),
    ]
    recorded = [
        _cause_decision("a", NO_SECTION, explanation=fp),
        _cause_decision("b", LATE, explanation=fp),
        _cause_decision("answered", "x", explanation=fp, answer="fix_cube"),
    ]
    mark_decided(run, items, recorded)

    a, b = cause_asks(run, {"items": items}, recorded)

    assert (a.decision.id, len(a.groups), a.rows) == ("a", 2, 57)
    assert (b.decision.id, len(b.groups), b.rows) == ("b", 1, 3)


def _write_run_sorted(tmp_path, run, items):
    run_json = tmp_path / "run.json"
    run_json.write_text("{}")
    (tmp_path / "sort.json").write_text(json.dumps(
        {"moment": _moment(run), "open": open_keys(run), "items": items,
         "formulas_not_compared": {},
         "posted_version": POSTED_VERSION}))  # fmt: skip
    return run_json


def test_the_gate_refuses_an_explained_group_or_cell_set_with_no_explanation(tmp_path):
    run = _fp_run(_groups("Newark"))
    (key,) = open_items(run)
    item = {**_item(key, None, ("cube", NO_SECTION, 30))}

    with pytest.raises(
        pipeline.Refusal, match="1 `cause` item rests on no explanation"
    ):
        checked_sort(run, _write_run_sorted(tmp_path, run, [item]))

    explanation = _explanation_file(tmp_path)
    checked_sort(
        run, _write_run_sorted(tmp_path, run, [{**item, "explanation": explanation}])
    )


def test_the_gate_takes_a_reconcile_or_workbook_explanation_and_no_bare_cause(tmp_path):
    run = _fp_run(_groups("Newark", bucket="dashboard_filtered"))
    run.applied.open_gaps = [_gap()]
    (key, gap) = open_items(run)
    items = [
        _item(key, {"kind": "reconcile"}, ("dashboard", "dashboard filter", 30)),
        {"id": gap.id, "kind": "gap", "comparison": "", "suggestion": "cause",
         "cause": [{"side": "dashboard", "label": "sheet filter x"}],
         "explanation": {"kind": "workbook"}},
    ]  # fmt: skip

    assert checked_sort(run, _write_run_sorted(tmp_path, run, items))["items"]

    items[1]["explanation"] = None
    with pytest.raises(
        pipeline.Refusal, match="1 `cause` item rests on no explanation"
    ):
        checked_sort(run, _write_run_sorted(tmp_path, run, items))


# --- T20: model docs as leads ------------------------------------------------

from cube_validation.sort import (  # noqa: E402
    _as_json,
    _from_json,
    doc_leads,
)


def test_doc_leads_name_the_model_docs_of_a_comparison(tmp_path):
    docs = tmp_path / "docs" / "models"
    docs.mkdir(parents=True)
    (docs / "a-data-model.md").write_text("Reads `rpt_tableau__x` and fct_f.\n")
    (docs / "b-data-model.md").write_text("Only fct_f here.\n")
    # A longer name that merely starts with the model's is not a mention.
    (docs / "c-data-model.md").write_text("rpt_tableau__x_archive\n")
    cfg = ViewConfig(
        view="v",
        fact="kipptaf_marts.fct_f",
        comparisons=[
            Comparison(
                id="one", measure="m", dashboard_view="kipptaf_tableau.rpt_tableau__x"
            ),
            Comparison(id="two", measure="m", dashboard_view="kipptaf_tableau.rpt_y"),
        ],
    )

    leads = doc_leads(cfg, docs)

    assert leads["one"] == (
        "lead: read docs/models/a-data-model.md (mentions rpt_tableau__x, fct_f), "
        "docs/models/b-data-model.md (mentions fct_f)"
    )
    assert leads["two"] == (
        "lead: read docs/models/a-data-model.md (mentions fct_f), "
        "docs/models/b-data-model.md (mentions fct_f)"
    )
    assert doc_leads(cfg, tmp_path / "none") == {}


def test_the_repo_s_ddi_doc_is_a_lead_for_its_dashboard():
    cfg = ViewConfig(
        view="v",
        fact="kipptaf_marts.fct_nothing_here",
        comparisons=[
            Comparison(
                id="ddi",
                measure="m",
                dashboard_view="kipptaf_tableau.rpt_tableau__ddi_dashboard",
            )
        ],
    )

    assert doc_leads(cfg)["ddi"] == (
        "lead: read docs/models/ddi-stack-data-model.md "
        "(mentions rpt_tableau__ddi_dashboard)"
    )


# --- T17 leftovers ------------------------------------------------------------


def test_closing_a_masked_sibling_moves_no_other_items_counts(tmp_path):
    # P and Q share a masked id: `#2` goes by raw dims, so P is `B#2`.
    p = Group("enrollment", (("region", "Paterson"),), "dashboard_only", 30, 4)
    q = Group("enrollment", (("region", "Camden"),), "dashboard_only", 20, 4)
    run = _fp_run([p, q])
    by_dims = {g.dims: it for it, g in zip(open_items(run), [p, q], strict=True)}
    explanation = _explanation_file(tmp_path)
    fp = explanation["fingerprint"]
    item = _item(by_dims[p.dims], explanation, ("cube", NO_SECTION, 30))
    recorded = [_cause_decision("a", NO_SECTION, explanation=fp)]
    assert item["id"].endswith("#2")

    # A `group` decision closes Q; P's id would now be the bare masked one.
    run.applied.open = [p]
    assert [i.id for i in open_items(run)] == [item["id"].removesuffix("#2")]
    mark_decided(run, [item], recorded)
    (ask,) = cause_asks(run, {"items": [item]}, recorded)

    assert item["decided"] is True
    assert ask.groups == [p] and ask.rows == 30


def test_a_quieted_dashboard_filtered_group_passes_the_explanation_gate(tmp_path):
    group = _groups("Newark", bucket="dashboard_filtered")[0]
    run = _fp_run([group])
    (it,) = open_items(run)
    item = _item(it, {"kind": "reconcile"}, ("dashboard", "dashboard filter", 30))
    # A `group` decision closed it after the sort: it is no longer open.
    run.applied.open = []
    run_json = _write_run_sorted(tmp_path, run, [item])

    assert checked_sort(run, run_json)["items"] == [item]


def test_decided_marks_round_trip_through_sort_json(tmp_path):
    run = _fp_run(_groups("Newark"))
    (it,) = open_items(run)
    explanation = _explanation_file(tmp_path)
    item = _item(it, explanation, ("cube", NO_SECTION, 30))
    item.update(evidence=["proof line"], evidence_posted=["proof line"])
    mark_decided(
        run,
        [item],
        [_cause_decision("a", NO_SECTION, explanation=explanation["fingerprint"])],
    )

    back = _as_json(_from_json(item))

    assert (back["decided"], back["decisions"]) == (True, {f"cube: {NO_SECTION}": "a"})
    assert back["key"] == it.key and back == item


# --- final review: sheet-filter causes, closed investigate items --------------

from cube_validation.answers import approved_decisions  # noqa: E402


def test_sheet_filtered_groups_share_one_cause_decision_and_no_group_stub(tmp_path):
    # DDI's C6: 6 groups the sheet's own filter drops, on 6 different modules.
    entry = {"dashboard": "administered_at", "operator": "lte", "days_from_week_end": 0}
    check = _rebuild_check(
        missing_columns={"Exclude Future Assessments": "administered_at"}
    )
    cmp = Comparison(id="enrollment", measure="m", dims=[ColumnPair("Module", "module_code")],
                     rebuild_check=check, dashboard_filters=[entry])  # fmt: skip
    cfg = ViewConfig(view="enrollment", fact="d.t", comparisons=[cmp])
    groups = [
        Group("enrollment", (("dashboard_filter", "administered_at"),
                             ("module_code", f"M{i}")), "dashboard_filtered", 12, 12)
        for i in range(6)
    ]  # fmt: skip
    run = _fp_run(groups)
    items = [_as_json(x) for x in suggest(cfg, run, {}, traces=None)]
    approved = [
        {"id": f"c6-{i}", "call": "deliberate", "reason": "the sheet hides them",
         "item": item["id"]}
        for i, item in enumerate(items)
    ]  # fmt: skip

    (decision,) = approved_decisions(approved, {"items": items}, {"enrollment": FPS})

    assert all("group" not in i["stub"] for i in items)
    assert decision["cause"] == {
        "side": "dashboard",
        "label": "sheet filter Exclude Future Assessments",
    }
    assert "group" not in decision
    assert (
        decision["fingerprints"]["explanation"]
        == items[0]["explanation"]["fingerprint"]
    )
    marked = [dict(i) for i in items]
    mark_decided(run, marked, [Decision(**decision)])
    assert all(i["decided"] for i in marked)


def test_a_decision_closing_an_item_sort_holds_in_investigate_refuses(tmp_path):
    group = _groups("Newark")[0]
    run = _fp_run([group])
    (it,) = open_items(run)
    item = {"id": it.id, "key": it.key, "kind": "group", "comparison": "enrollment",
            "suggestion": "investigate", "cause": None, "explanation": None}  # fmt: skip
    hand = Decision("hand", "enrollment", "deliberate", "r",
                    group={"column": "region", "values": ["Newark"]},
                    fingerprints=dict(FPS))  # fmt: skip
    # Written by hand after the sort, then re-applied: the group is now quiet.
    run.applied = Applied(quiet=[(hand, group)])
    run_json = _write_run_sorted(tmp_path, run, [item])

    with pytest.raises(
        pipeline.Refusal,
        match=r"decision 'hand' closes item .* `investigate`.*see `explain` in the "
        "cube-validation skill",
    ):
        checked_sort(run, run_json)


# --- closed groups: what a cause decision covers past the sort's items ---------

from collections import Counter  # noqa: E402
from pathlib import Path  # noqa: E402

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.sort import (  # noqa: E402
    _entries,
    _open_key,
    check_closed,
    closed_groups,
    with_closed,
)


def _ran_over(run, cause="C1"):
    """A stored explanation's run over `with_closed(run)` explaining every group."""
    path = Path("v") / "explanations" / "v" / "enrollment__dashboard_only.sql"
    explanation = explain.Explanation(path, "enrollment", "dashboard_only",
                                {cause: ("cube", NO_SECTION)}, "SELECT 1")  # fmt: skip
    items = [(i.id, g) for i, g in _entries(with_closed(run))]
    found = {i: explain.Outcome(g.n_rows, Counter({cause: g.n_rows})) for i, g in items}
    return explanation, explain.Ran(explanation, items, found)


def test_closed_groups_keep_open_ids_and_classify_the_closed_one(tmp_path):
    # P and Q share a masked id: listed together, P would be `#2`.
    p = Group("enrollment", (("region", "Paterson"),), "dashboard_only", 30, 4)
    q = Group("enrollment", (("region", "Camden"),), "dashboard_only", 20, 4)
    run = _fp_run([p])
    run.applied.quiet = [(_group_decision("fix_cube"), q)]
    (p_item,) = open_items(run)
    explanation, ran = _ran_over(run)
    assert {i for i, _ in ran.items} == {p_item.id, f"{p_item.id}#2"}

    (kept,), (closed,) = closed_groups(run, [ran], _cfg())

    assert kept.items == [(p_item.id, p)] and list(kept.found) == [p_item.id]
    assert closed == {
        "id": _open_key(q), "key": _open_key(q), "kind": "group",
        "comparison": "enrollment", "closed": True, "suggestion": "cause",
        "cause": [{"side": "cube", "step": "C1", "label": NO_SECTION, "n_rows": 20}],
        "explanation": {"kind": "query", "path": explanation.recorded,
                  "fingerprint": explanation.fingerprint},
    }  # fmt: skip


def test_a_run_over_closed_groups_alone_is_not_an_open_items_run():
    q = _groups("Camden")[0]
    run = _fp_run([])
    run.applied.quiet = [(_group_decision("fix_cube"), q)]
    _, ran = _ran_over(run)

    kept, closed = closed_groups(run, [ran], _cfg())

    assert kept == [] and [c["key"] for c in closed] == [_open_key(q)]


def test_check_closed_says_when_no_sort_lets_it_run(tmp_path, capsys):
    run = _fp_run([])

    check_closed(run, tmp_path / "run.json", [])

    assert "closed-group check skipped" in capsys.readouterr().err


@pytest.mark.parametrize("call", ["fix_cube", "deliberate"])
def test_check_closed_compares_a_cause_with_the_group_decision_closing_it(
    tmp_path, call
):
    q = _groups("Newark")[0]
    run = _fp_run([])
    group_decision = _group_decision("fix_cube")
    run.applied.quiet = [(group_decision, q)]
    explanation, ran = _ran_over(run)
    _, closed = closed_groups(run, [ran], _cfg())
    run_json = _write_run_sorted(tmp_path, run, [])
    loaded = json.loads((tmp_path / "sort.json").read_text())
    (tmp_path / "sort.json").write_text(json.dumps({**loaded, "closed": closed}))
    cause = _cause_decision(
        "a", NO_SECTION, call=call, explanation=explanation.fingerprint
    )

    if call == "fix_cube":
        check_closed(run, run_json, [group_decision, cause])
        return
    with pytest.raises(pipeline.Refusal) as refused:
        check_closed(run, run_json, [group_decision, cause])
    assert str(refused.value) == (
        "decisions 'by-region' (fix_cube) and 'a' (deliberate) disagree on a group "
        "of 'enrollment' that 'by-region' closes by 'region'"
    )
    # The review gate reads the same list.
    with pytest.raises(pipeline.Refusal, match="closes by 'region'"):
        checked_sort(run, run_json, [group_decision, cause])


# --- each comparison's latest result --------------------------------------------

from dataclasses import replace  # noqa: E402

from cube_validation import latest  # noqa: E402
from cube_validation.sort import comparisons_waiting  # noqa: E402


def test_a_recomposed_run_needs_a_new_sort(tmp_path):
    # Another comparison's result moved to a newer moment: the run's own moment
    # is unchanged, but its sort was of the earlier composition.
    run = _fp_run(_groups("Newark"))
    run.moments = {"enrollment": run.moment}
    run_json = _write_run_sorted(tmp_path, run, [])
    later = Build(START.replace(day=28), END.replace(day=28), "j2")

    recomposed = replace(run, moments={**run.moments, "other": later})

    with pytest.raises(pipeline.Refusal, match="sort.json is of another moment"):
        checked_sort(recomposed, run_json)


def test_waiting_comparisons_name_the_missing_the_stale_and_the_edited():
    c1, c2, c3, c4 = (
        Comparison(id=f"c{i}", measure="m", confirmed=True) for i in range(1, 5)
    )
    cfg = ViewConfig(view="v", fact="d.t", comparisons=[c1, c2, c3, c4])
    run = replace(
        _run(),
        missing=["c1"],
        entries={
            "c2": latest.entry_fingerprint(c2),
            "c3": "an older entry",
            "c4": latest.entry_fingerprint(c4),
        },
    )
    loaded = {"stale": {"c2": "Cube's SQL changed"}}

    assert comparisons_waiting(cfg, run, loaded) == {
        "c1": "never compared",
        "c2": "Cube's SQL changed",
        "c3": "its entry or rebuild check changed",
    }


def test_waiting_comparisons_name_a_skipped_one_by_why_it_was_skipped():
    c1, c2 = (Comparison(id=f"c{i}", measure="m", confirmed=True) for i in (1, 2))
    cfg = ViewConfig(view="v", fact="d.t", comparisons=[c1, c2])
    run = replace(
        _run(),
        missing=["c1"],
        entries={"c2": latest.entry_fingerprint(c2)},
        skipped=[
            {"comparison": "c1", "why": "no explanation; run `rebuild-sheet` first"},
            {"comparison": "c2", "why": "workbook changed since its rebuild check"},
        ],
    )

    assert comparisons_waiting(cfg, run, {}) == {
        "c1": "not compared: no explanation; run `rebuild-sheet` first",
        "c2": "not compared: workbook changed since its rebuild check",
    }


def test_the_gate_returns_items_in_investigate_as_unsettled(tmp_path):
    run = _fp_run(_groups("Newark", "Camden"))
    newark, camden = open_items(run)
    explained = _item(newark, _explanation_file(tmp_path), ("cube", NO_SECTION, 30))
    left = {**_item(camden, None), "suggestion": "investigate", "cause": None}

    loaded = checked_sort(run, _write_run_sorted(tmp_path, run, [explained, left]))

    assert [i["id"] for i in loaded["unsettled"]] == [camden.id]
    assert [i["id"] for i in loaded["items"]] == [newark.id, camden.id]


# --- sheet filters Cube might not offer (#6346) -------------------------------


def test_a_filter_that_filters_nothing_still_names_its_candidate_member():
    cfg = _cfg(restricting_filters=["Region"], filter_notes={"Region": "copy of Grade"})
    docs = {"v_region": _doc("v_region", title="Region")}

    [s] = suggest(cfg, _run(gaps=[_gap("Region")]), docs)

    assert s.suggestion == "filters_nothing"
    assert s.evidence[0].startswith("Cube offers it as `v_region`")
    assert "check before mapping" in s.evidence[0]
    assert s.default_call == ""


def test_a_filter_with_no_member_and_no_column_is_workbook_only():
    cfg = _cfg(restricting_filters=["Enroll Status"])

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.evidence[0] == "Workbook-only field: no datasource column behind it"
    assert s.default_call == "deliberate"


def test_a_filter_with_a_column_and_no_member_is_a_gap_for_cube():
    cfg = _cfg(
        restricting_filters=["Enroll Status"],
        missing_columns={"Enroll Status": "enroll_status"},
    )

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.evidence[0] == "Cube has no member: a gap"
    assert s.default_call == "fix_cube"


def test_a_candidate_beats_workbook_only():
    cfg = _cfg(restricting_filters=["Region"])
    docs = {
        "v_region": _doc("v_region", title="Region"),
        "v_zone": _doc("v_zone", description="Region zone"),
    }

    [s] = suggest(cfg, _run(gaps=[_gap("Region")]), docs)

    assert s.evidence[0] == (
        "Cube offers it as `v_region`, `v_zone`, unmapped: "
        "check before mapping it under `filters:`"
    )
    assert s.default_call == ""
    assert not any("Workbook-only" in line for line in s.evidence)


def test_a_cut_gap_gets_no_filter_label():
    cfg = _cfg(restricting_filters=["Week"])

    [s] = suggest(cfg, _run(gaps=[_gap("Week", "cut")]), {})

    assert s.default_call == ""
    assert not s.evidence[0].startswith(("Cube ", "Workbook-only"))


def test_the_default_call_round_trips_through_sort_json():
    cfg = _cfg(restricting_filters=["Enroll Status"])
    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    d = _as_json(s)

    assert d["default_call"] == "deliberate"
    assert _from_json(d).default_call == "deliberate"
    assert (
        _from_json({k: v for k, v in d.items() if k != "default_call"}).default_call
        == ""
    )


def test_the_batch_prints_the_default_call():
    cfg = _cfg(restricting_filters=["Enroll Status"])
    run = _run(gaps=[_gap()])
    found = suggest(cfg, run, {})

    assert "    default call: deliberate" in batch_lines(run, found)


def test_a_filter_that_filters_nothing_with_a_column_and_no_member_is_a_gap():
    cfg = _cfg(
        restricting_filters=["Grade"],
        missing_columns={"Enroll Status": "enroll_status"},
    )

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.suggestion == "filters_nothing"
    assert s.evidence[0] == "Cube has no member: a gap"
    assert s.default_call == "fix_cube"


def test_the_filter_label_is_also_the_first_posted_line():
    cfg = _cfg(
        restricting_filters=["Enroll Status"],
        missing_columns={"Enroll Status": "enroll_status"},
    )

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.posted[0] == s.evidence[0] == "Cube has no member: a gap"


def test_another_comparisons_column_never_makes_a_gap_for_cube():
    mine = Comparison(
        id="enrollment",
        measure="student_count",
        dims=[ColumnPair("Grade", "grade_level")],
        rebuild_check=_rebuild_check(restricting_filters=["Enroll Status"]),
    )
    other = Comparison(
        id="attendance",
        measure="student_count",
        dims=[ColumnPair("Grade", "grade_level")],
        rebuild_check=_rebuild_check(
            restricting_filters=["Enroll Status"],
            missing_columns={"Enroll Status": "enroll_status"},
        ),
    )
    cfg = ViewConfig(view="enrollment", fact="d.t", comparisons=[mine, other])

    [s] = suggest(cfg, _run(gaps=[_gap()]), {})

    assert s.evidence[0] == "Workbook-only field: no datasource column behind it"
    assert s.default_call == "deliberate"


def test_a_filter_gap_looks_up_its_candidates_once(monkeypatch):
    from cube_validation import sort

    calls = []
    real = sort._candidates

    def counted(caption, docs):
        calls.append(caption)
        return real(caption, docs)

    monkeypatch.setattr(sort, "_candidates", counted)
    cfg = _cfg(restricting_filters=["Region"])
    docs = {"v_region": _doc("v_region", title="Region")}

    [s] = suggest(cfg, _run(gaps=[_gap("Region")]), docs)

    assert s.candidates == ("v_region",)
    assert calls == ["Region"]
