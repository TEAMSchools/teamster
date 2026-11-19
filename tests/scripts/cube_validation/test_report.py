import dataclasses
import json
import re
from datetime import datetime, timezone

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation import compare, pipeline, report

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.answers import questions_json

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, Decision, ViewConfig

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.decisions import Applied
from cube_validation.moment import Build

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.reconcile import CellDiff, Gap, Group

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.report import (
    CauseAsk,
    MeasureResult,
    RunResult,
    mask,
    render_local,
    render_review_issue,
    save_local,
    suppress,
)

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation


START = datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc)
END = datetime(2026, 10, 27, 6, 5, 30, tzinfo=timezone.utc)


def _decision(call="domain_owner", id="d1", column="region", values=("Newark",)):
    return Decision(
        id=id,
        comparison="enrollment",
        call=call,
        reason="Registrar owns the rule",
        group={"column": column, "values": list(values)},
        task="https://app.asana.com/0/1/2",
    )


def _run(**overrides):
    quiet_group = Group("enrollment", (("region", "Newark"),), "value_differs", 40, 12)
    id_group = Group("enrollment", (("student_number", "123456"),), "cube_only", 2, 2)
    other_group = Group("enrollment", (("region", "Camden"),), "value_differs", 5, 5)
    open_group = Group("enrollment", (("grade_level", "9"),), "value_differs", 40, 38)
    applied = Applied(
        open=[open_group],
        quiet=[
            (_decision(), quiet_group),
            # Its own reason, so it stays its own bullet.
            (
                dataclasses.replace(
                    _decision(id="d2", column="student_number", values=("123456",)),
                    reason="Ids differ",
                ),
                id_group,
            ),
            (_decision(call="deliberate", id="d3"), other_group),
        ],
        reconfirm=[_decision(id="d4")],
        no_longer_needed=[_decision(id="d5")],
    )
    base = dict(
        view="enrollment_view",
        moment=Build(START, END, "job-1"),
        measures=[
            MeasureResult("enrolled", "validated", {"pass": 12}),
            MeasureResult("withdrawn", "differs", {"pass": 10, "differs": 1}),
            MeasureResult("seats", "differs", {"pass": 1, "differs": 1}),
        ],
        applied=applied,
        live_sources=["kipptaf_extracts.rpt_enrollment"],
        changed_dims=["dim_students"],
        scopes=["region = Newark"],
        cost_usd=0.42,
        proofs={"enrollment": "2026-10-20"},
        browser_cuts=["Region = Newark, Grade = 9"],
        clauses={"enrollment": ["WHERE grade_level > 8"]},
    )
    base.update(overrides)
    return RunResult(**base)


def test_mask_small_counts():
    assert mask(9) == "<10" and mask(10) == "10"
    assert mask(0) == "<10"


def test_measure_line_names_open_row_groups():
    measures = [
        MeasureResult("enrolled", "validated", {"pass": 135}, 2),
        MeasureResult("left", "validated", {"pass": 3}, 1),
        MeasureResult("clean", "validated", {"pass": 4}),
    ]
    text = render_local(_run(measures=measures))
    assert ("- `enrolled`: validated (pass 135); 2 open row groups to sort") in text
    assert "validated (pass 3); 1 open row group to sort" in text
    assert "- `clean`: validated (pass 4)\n" in text


def test_local_result_names_partly_stale_values():
    applied = Applied(partly_stale=[(_decision(id="d6"), ["Camden", "Miami"])])

    text = render_local(_run(applied=applied))

    section = text.split("No longer needed")[1].split("Fingerprints")[0]
    assert (
        "`d6` (enrollment, domain_owner): Registrar owns the rule; "
        "partly no longer needed: Camden, Miami"
    ) in section


def test_partly_stale_empty_value_reads_as_empty():
    applied = Applied(partly_stale=[(_decision(id="d6"), ["", "Miami"])])

    text = render_local(_run(applied=applied))

    assert "partly no longer needed: (empty), Miami" in text


def test_local_result_lists_live_sources_and_changed_dims():
    text = render_local(_run())
    assert "kipptaf_extracts.rpt_enrollment" in text
    assert "dim_students" in text
    assert "region = Newark" in text
    assert "Region = Newark, Grade = 9" in text
    assert "0.42" in text


def test_local_result_section_order_and_triage():
    text = render_local(_run())
    heads = [
        "## Measures",
        "## Sort",
        "## Decisions",
        "## Sources read live",
        "## Dimensions that changed",
        "## Scopes",
        "## Cuts to check in the browser",
        "## Cost",
    ]
    positions = [text.index(h) for h in heads]
    assert positions == sorted(positions)
    assert "WHERE grade_level > 8" in text
    assert "40" in text and "38" in text
    assert "123456" not in text  # not a triage group, so not listed


def test_local_result_is_not_masked():
    text = render_local(_run())
    assert "40 rows, 38 students" in text
    assert "<10" not in text


def test_review_issue_has_no_raw_small_counts():
    body = render_review_issue("Registrar", [_run()])
    assert "40 rows, 12 students" in body
    assert "<10 rows, <10 students" in body
    assert "Camden" not in body  # deliberate group, not domain owner


def test_review_issue_structure_and_redaction():
    body = render_review_issue("Registrar", [_run()])
    assert body.index("## What and why") < body.index("## Proposed approach")
    assert body.index("## Proposed approach") < body.index(
        "<details>\n<summary>For Claude</summary>"
    )
    assert body.rstrip().endswith("</details>")
    assert "123456" not in body
    assert "student_number" in body and "<redacted>" in body
    assert "Newark" in body
    assert "withdrawn" not in body and "enrolled" not in body


def _issue_with(group, reason="ok", measures=None):
    d = Decision(
        "dx",
        "enrollment",
        "domain_owner",
        reason,
        {"column": group.dims[0][0], "values": [group.dims[0][1]]},
    )
    run = _run(applied=Applied(quiet=[(d, group)]))
    if measures is not None:
        run.measures = measures
    return render_review_issue("Registrar", [run])


def test_review_issue_bullets_stay_on_one_line():
    g = Group("enrollment", (("region", "New\nark"),), "value_differs", 40, 12)
    body = _issue_with(g, reason="line one\n  line two\n\nline three")
    bullets = [x for x in body.splitlines() if x.startswith("- ")]
    assert bullets and all(
        "Reason: line one line two line three" in b for b in bullets[:1]
    )
    assert "line two" in body and "\n  line two" not in body
    assert "- Q1. `region` = `New ark`" in body


def test_columns_off_the_reviewed_list_redacted():
    for col in (
        "foo",
        "firstlast",
        "attendance_value",
        "last_name",
        "ssid",
        "leaid",
        "email",
        "dob",
        "student_number",
        "state_id",
        "local_id",
        "sid",
        "id",
        "region_id",
        "first_name",
        "full_name",
        "student_name",
        "lastfirst",
        "name",
        "teacher_name",
        "username",
        "student_school_name",
        "section_name",
        "course_name",
        "school_name_alt",
        "school_name",
        "foo_name",
    ):
        g = Group("enrollment", ((col, "SECRETVAL"),), "cube_only", 50, 50)
        assert "SECRETVAL" not in _issue_with(g), col


def test_reviewed_columns_shown_at_10_students():
    for col in (
        "regions_region_name",
        "locations_abbreviation",
        "school_abbreviation",
        "locations_location_name",
        "region",
        "grade_level",
    ):
        big = Group("enrollment", ((col, "Camden"),), "cube_only", 50, 10)
        small = Group("enrollment", ((col, "Camden"),), "cube_only", 50, 9)
        assert f"`{col}` = `Camden`" in _issue_with(big), col
        assert f"`{col}` = `<redacted>`" in _issue_with(small), col


def test_small_group_on_harmless_column_redacted():
    small = Group("enrollment", (("grade_level", "9"),), "cube_only", 50, 9)
    big = Group("enrollment", (("grade_level", "9"),), "cube_only", 50, 10)
    assert "`grade_level` = `<redacted>`" in _issue_with(small)
    assert "`grade_level` = `9`" in _issue_with(big)


def test_reason_is_sanitized():
    g = Group("enrollment", (("region", "Newark"),), "value_differs", 40, 12)
    body = _issue_with(g, reason="Student 123456 moved to Newark.")
    assert "123456" not in body
    # Newark is a reviewed value the issue shows anyway; the id is not.
    assert "Reason: Student <redacted> moved to Newark." in body


def test_reason_with_unquoted_numeric_values():
    g = Group("enrollment", (("grade_level", "9"),), "value_differs", 40, 12)
    d = Decision(
        "dx", "enrollment", "domain_owner", "Grade 9 is split",
        {"column": "grade_level", "values": [9]},
    )  # fmt: skip
    body = render_review_issue("Registrar", [_run(applied=Applied(quiet=[(d, g)]))])
    assert "Reason: Grade 9 is split" in body


def test_separated_ids_in_reason_redacted():
    g = Group("enrollment", (("region", "Newark"),), "value_differs", 40, 12)
    for raw in ("12-345", "1234 5678", "12,345,678", "12 345", "2026-10-22"):
        body = _issue_with(g, reason=f"Student {raw} moved.")
        assert raw not in body
        assert "Reason: Student <redacted> moved." in body
    assert "Reason: Grade 9 of 12 moved." in _issue_with(
        g, reason="Grade 9 of 12 moved"
    )


def test_save_local_writes_under_moment(tmp_path):
    run = _run()
    path = save_local(run, "hello", root=tmp_path)
    assert path == tmp_path / "enrollment_view" / "2026-10-27T060530Z" / "result.md"
    assert path.read_text() == "hello"


def test_review_issue_names_every_dim_and_masks_each():
    g = Group(
        "enrollment",
        (("regions_region_name", "Camden"), ("student_number", "SECRETVAL")),
        "value_differs",
        40,
        12,
    )
    body = _issue_with(g, reason="Camden SECRETVAL rows")
    assert "- Q1. `regions_region_name` = `Camden` in enrollment" in body
    assert "SECRETVAL" not in body
    assert "Reason: Camden <redacted> rows" in body


GAP_TEAM = Gap("cut", "Team", ("Roster",), ("tardy-roster", "absent-roster"))
GAP_ENROLL = Gap("filter", "Enroll Status", ("Roster",), ("tardy-roster",), True)


def _gap_decision(call="domain_owner"):
    return Decision(
        id="g1", comparison="", call=call, reason="owner decides the cut",
        task="#6150", missing_cut="Team",
    )  # fmt: skip


def test_local_result_lists_missing_cuts_and_filters():
    run = _run(applied=Applied(open_gaps=[GAP_TEAM, GAP_ENROLL]))
    run.gaps_unknown = ["ada: missing cuts and filters unknown; re-run `rebuild-sheet`"]
    text = render_local(run)
    section = text.split("## Missing cuts and filters", 1)[1].split("## ", 1)[0]
    assert (
        "`Team` (cut) on Roster: Cube has no member; tardy-roster, absent-roster"
        in section
    )
    assert (
        "`Enroll Status` (filter, set to chosen values, not All) on Roster" in section
    )
    assert "ada: missing cuts and filters unknown; re-run `rebuild-sheet`" in section


def test_measure_line_counts_open_missing_cuts():
    run = _run()
    run.measures[0].open_gaps = 2
    assert "2 missing cuts or filters to sort" in render_local(run)


def test_gap_decision_line_names_the_field():
    run = _run(applied=Applied(quiet_gaps=[(_gap_decision("deliberate"), GAP_TEAM)]))
    assert "`g1` (missing cut `Team`, deliberate)" in render_local(run)


def test_review_issue_carries_domain_owner_missing_cuts():
    run = _run(applied=Applied(quiet_gaps=[(_gap_decision(), GAP_TEAM)]))
    body = render_review_issue("Registrar", [run])
    assert (
        "`Team` on `Roster` in `enrollment_view`: a sheet cut Cube has no member "
        "for. Reason: owner decides the cut. Task: #6150" in body
    )
    assert "Missing cuts and filters: 1." in body


def test_review_issue_reports_other_missing_cut_calls_without_asking():
    run = _run(applied=Applied(quiet_gaps=[(_gap_decision("fix_cube"), GAP_TEAM)]))

    body = render_review_issue("Registrar", [run])

    asked, also = body.split("Also decided (no answer needed)")
    assert "`Team`" not in asked and "Missing cuts and filters: 0." in body
    assert (
        "- `Team` on `Roster` in `enrollment_view`: a sheet cut Cube has no member "
        "for: Cube gets fixed (`fix_cube`). Reason: owner decides the cut. "
        "Task: #6150"
    ) in also


def test_a_cause_and_a_missing_filter_decided_alike_show_as_one_line():
    gap = _gap_decision("deliberate")
    cause = dataclasses.replace(
        gap, id="c1", comparison="enrollment", missing_cut=None,
        cause={"side": "dashboard", "label": "sheet filter team"},
    )  # fmt: skip
    run = _run(applied=Applied(quiet_gaps=[(gap, GAP_TEAM)]))
    decided = {"enrollment_view": [CauseAsk(cause, [], 0)]}

    body = render_review_issue("Registrar", [run], decided=decided)

    also = [x for x in body.split("Also decided")[1].splitlines() if "Reason" in x]
    assert also == [
        "- cause `sheet filter team` on the dashboard side (`enrollment` in "
        "`enrollment_view`) and `Team` on `Roster` in `enrollment_view`: a sheet "
        "cut Cube has no member for: an intended difference; later runs stay "
        "quiet on it (`deliberate`). Reason: owner decides the cut. Task: #6150"
    ]


def test_scoped_run_says_scope_narrows_the_measure():
    note = "Scope filters Cube's measure query, not only its rows"
    assert note not in render_local(_run(scopes=[]))
    assert note in render_local(_run(scopes=["c: membership_value in 1"]))


TARDY_DEFS = {
    "enrollment": {"dashboard": "codes ET, T", "cube": "codes T% (student 123456)"}
}


def test_review_issue_shows_definitions_side_by_side():
    run = _run()
    body = render_review_issue(
        "Registrar", [run], definitions={"enrollment_view": TARDY_DEFS}
    )
    section = body.split("Definitions side by side", 1)[1]
    assert "`enrollment` in `enrollment_view`" in section
    assert "Dashboard: codes ET, T" in section
    assert "Cube: codes T% (student <redacted>)" in section
    assert "123456" not in body


def test_review_issue_skips_definitions_with_no_owner_question():
    run = _run(applied=Applied())
    body = render_review_issue(
        "Registrar", [run], definitions={"enrollment_view": TARDY_DEFS}
    )
    assert "Definitions side by side" not in body


def test_proof_dates_sit_apart_from_browser_cuts():
    text = render_local(_run(browser_cuts=[], proofs={"ada": "2026-10-27T19:00"}))
    cuts = text.split("## Cuts to check in the browser", 1)[1].split("## ", 1)[0]
    assert "ada" not in cuts and "None." in cuts
    proofs = text.split("## Rebuild checks", 1)[1].split("## ", 1)[0]
    assert "ada: last matched 2026-10-27T19:00" in proofs


def test_local_result_lists_domain_owner_decisions_without_a_task():
    d = Decision(
        "owner-1", "enrollment", "domain_owner", "owner decides",
        {"column": "region", "values": ["Newark"]},
    )  # fmt: skip
    g = Group("enrollment", (("region", "Newark"),), "value_differs", 40, 12)
    text = render_local(_run(applied=Applied(quiet=[(d, g)])))
    assert "Fill in `task` once the review issue posts: `owner-1`" in text


TARDY_DIFF = CellDiff(
    "enrollment",
    {"differs": 58, "dashboard_only": 3},
    ("58 cells: values differ beyond rounding", "3 of 61 in cut {}"),
)


def test_local_result_lists_cell_differences_with_candidate_causes():
    run = _run(applied=Applied(open_cells=[TARDY_DIFF]))
    run.measures[0].open_cells = 1
    text = render_local(run)
    section = text.split("## Cell differences", 1)[1].split("## ", 1)[0]
    assert "enrollment: 58 differ, 3 dashboard only" in section
    assert "  - 58 cells: values differ beyond rounding" in section
    assert "cell differences to sort in 1 comparison" in text


def _formula(id, comparison, reason, **kw):
    return Decision(id, comparison, "domain_owner", reason, formula=True, **kw)


def _formula_diff(comparison, n):
    return CellDiff(comparison, {"differs": n}, kind="formula")


FORMULA_ASK = "cells differ while every row in them matches; which definition is right?"


def test_a_formula_question_shows_both_definitions_and_masks_its_count():
    d = _formula("formula-1", "enrollment", "owner picks codes")
    small = dataclasses.replace(TARDY_DIFF, kind="formula")
    run = _run(applied=Applied(quiet_cells=[(d, small)]))
    body = render_review_issue(
        "Registrar", [run], definitions={"enrollment_view": TARDY_DEFS}
    )
    assert f"- Q1. `enrollment` in `enrollment_view`: 61 {FORMULA_ASK} Reason:" in body
    assert "Reason: owner picks codes" in body
    section = body.split("Definitions side by side", 1)[1]
    assert "Dashboard: codes ET, T" in section and "Cube: codes T%" in section
    # Candidate causes stay local: they can name a cut or a value.
    assert "values differ beyond rounding" not in body
    assert "Formula differences: 1" in body

    few = Applied(quiet_cells=[(d, _formula_diff("enrollment", 4))])
    body = render_review_issue("Registrar", [_run(applied=few)])
    assert f"`enrollment` in `enrollment_view`: <10 {FORMULA_ASK}" in body
    assert "4 cells" not in body
    q = report._questions([_run(applied=few)])[0]
    assert q["kinds"] == ["formula"]
    assert report.defined_comparisons([q], "enrollment_view") == {"enrollment"}


def test_review_question_says_its_sheet_is_on_no_published_dashboard():
    d = _formula("formula-1", "enrollment", "owner picks codes")
    run = _run(applied=Applied(quiet_cells=[(d, _formula_diff("enrollment", 40))]))

    body = render_review_issue(
        "Registrar", [run], unpublished={"enrollment_view": {"enrollment"}}
    )
    assert "`enrollment`'s sheet is on no published dashboard" in body
    other = render_review_issue(
        "Registrar", [run], unpublished={"enrollment_view": {"other"}}
    )
    assert "no published dashboard" not in other


def test_group_and_cause_questions_say_their_sheet_is_on_no_published_dashboard():
    # A domain-owner row group on `enrollment`.
    group = render_review_issue(
        "Registrar", [_run()], unpublished={"enrollment_view": {"enrollment"}}
    )
    (line,) = [x for x in group.splitlines() if "Q1." in x]
    assert line.endswith(" Note: `enrollment`'s sheet is on no published dashboard.")

    run = _run(applied=Applied())
    causes = _cause_asks(["Team filter was set by hand"])
    cause = render_review_issue(
        "Registrar",
        [run],
        causes=causes,
        unpublished={"enrollment_view": {"cmp-1"}},
    )
    (line,) = [x for x in cause.splitlines() if "Q1." in x]
    assert line.endswith(" Note: `cmp-1`'s sheet is on no published dashboard.")


def test_a_formula_decision_reads_as_such_locally():
    d = _formula("formula-1", "enrollment", "owner picks codes")
    text = render_local(_run(applied=Applied(quiet_cells=[(d, TARDY_DIFF)])))
    assert "`formula-1` (enrollment formula, domain_owner): owner picks codes" in text
    open_formula = dataclasses.replace(TARDY_DIFF, kind="formula")
    text = render_local(_run(applied=Applied(open_cells=[TARDY_DIFF, open_formula])))
    section = text.split("## Cell differences", 1)[1].split("## ", 1)[0]
    assert "- enrollment: 58 differ, 3 dashboard only\n" in section
    assert "- enrollment formula difference: 58 differ, 3 dashboard only" in section


ENROLLED_REASON = "The dashboard counts enrolled students only (enroll_status = 0)"


def _enrolled_only(task=""):
    d = Decision(
        "tardy-enrolled", "tardy-roster", "domain_owner", ENROLLED_REASON,
        {"column": "dashboard_filter", "values": ["enroll_status"]}, task=task,
    )  # fmt: skip
    groups = [
        Group("tardy-roster", (("dashboard_filter", "enroll_status"), ("grade_level", str(i))),
              "dashboard_filtered", 10, 10)
        for i in range(13)
    ]  # fmt: skip
    return [(d, g) for g in groups]


def test_review_issue_prints_one_bullet_per_decision():
    body = render_review_issue(
        "Registrar", [_run(applied=Applied(quiet=_enrolled_only()))]
    )
    bullets = [x for x in body.splitlines() if x.startswith("- Q1. `dashboard_filter`")]
    assert bullets == [
        "- Q1. `dashboard_filter` = `enroll_status` in tardy-roster of `enrollment_view` "
        "(dashboard_filtered): 13 row groups, 130 rows, at least 10 students. "
        "Reason: " + ENROLLED_REASON + "."
    ]


def test_review_issue_keeps_reviewed_values_in_a_reason():
    d = Decision("newark", "enrollment", "domain_owner", "Some Newark students moved",
                 {"column": "region", "values": ["Newark"]})  # fmt: skip
    g = Group("enrollment", (("region", "Newark"),), "value_differs", 40, 12)
    body = render_review_issue("Registrar", [_run(applied=Applied(quiet=[(d, g)]))])
    assert "Reason: Some Newark students moved." in body
    assert "<redacted>" not in body.split("## Proposed approach")[0]


def test_review_issue_adds_no_period_after_a_question():
    q = "Should TD count as tardy?"
    d = _formula("td", "enrollment", q)
    diff = _formula_diff("enrollment", 58)
    body = render_review_issue(
        "Registrar", [_run(applied=Applied(quiet_cells=[(d, diff)]))]
    )
    assert f"Reason: {q}\n" in body + "\n" and "?." not in body
    tasked = _formula("td", "enrollment", q, task="#6200")
    body = render_review_issue(
        "Registrar", [_run(applied=Applied(quiet_cells=[(tasked, diff)]))]
    )
    assert f"Reason: {q} Task: #6200" in body


def test_review_issue_counts_questions_and_lists_every_decision():
    cells = _formula("tardy-cells", "tardy-roster", "codes?")
    gap = _gap_decision()
    run = _run(
        applied=Applied(
            quiet=_enrolled_only(),
            quiet_cells=[(cells, _formula_diff("tardy-roster", 58))],
            quiet_gaps=[(gap, GAP_TEAM)],
        )
    )
    body = render_review_issue("Registrar", [run])
    # 3 decisions, however many groups they cover.
    assert "owns the rule behind 3 questions" in body
    fold = body.split("<summary>For Claude</summary>", 1)[1]
    for decision_id in ("tardy-enrolled", "tardy-cells", "g1"):
        assert f"`{decision_id}`" in fold


def test_a_small_group_hides_its_value_in_the_reason_too():
    d = Decision("newark", "enrollment", "domain_owner", "Some Newark students moved",
                 {"column": "region", "values": ["Newark"]})  # fmt: skip
    g = Group("enrollment", (("region", "Newark"),), "cube_only", 39, 3)
    body = render_review_issue("Registrar", [_run(applied=Applied(quiet=[(d, g)]))])
    assert "- Q1. `region` = `<redacted>`" in body
    assert "Reason: Some <redacted> students moved." in body
    assert "Newark" not in body.split("## Proposed approach")[0]


def test_each_value_needs_10_students_of_its_own():
    d = Decision("two", "enrollment", "domain_owner", "Newark and Camden moved",
                 {"column": "region", "values": ["Newark", "Camden"]})  # fmt: skip
    big = Group("enrollment", (("region", "Newark"),), "cube_only", 400, 40)
    small = Group("enrollment", (("region", "Camden"),), "cube_only", 30, 3)
    body = render_review_issue(
        "Registrar", [_run(applied=Applied(quiet=[(d, big), (d, small)]))]
    )
    assert "- Q1. `region` = `Newark, <redacted>`" in body
    assert "Reason: Newark and <redacted> moved." in body
    assert "Camden" not in body.split("## Proposed approach")[0]


LEFT = "Owner: should Cube's default answer include students who left?"


def _left(comparison, students=20):
    d = Decision(
        f"{comparison}-left", comparison, "domain_owner", LEFT,
        {"column": "dashboard_filter", "values": ["enroll_status"]},
    )  # fmt: skip
    g = Group(comparison, (("dashboard_filter", "enroll_status"), ("grade_level", "9")),
              "dashboard_filtered", students * 10, students)  # fmt: skip
    return d, g


def test_review_issue_merges_decisions_that_share_a_reason():
    quiet = [_left("tardy-roster"), _left("absences-roster")]
    body = render_review_issue("Registrar", [_run(applied=Applied(quiet=quiet))])
    bullets = [x for x in body.splitlines() if LEFT in x]
    assert bullets == [
        "- Q1. `dashboard_filter` = `enroll_status` in absences-roster, tardy-roster of "
        "`enrollment_view` (dashboard_filtered): 2 row groups, 400 rows, "
        "at least 20 students in one comparison. "
        "Reason: " + LEFT
    ]
    fold = body.split("<summary>For Claude</summary>", 1)[1]
    assert "`tardy-roster-left`" in fold and "`absences-roster-left`" in fold


def test_merged_values_still_need_10_students_each():
    a = Decision(
        "a", "c1", "domain_owner", "same", {"column": "region", "values": ["Newark"]}
    )
    b = Decision(
        "b", "c2", "domain_owner", "same", {"column": "region", "values": ["Camden"]}
    )
    quiet = [
        (a, Group("c1", (("region", "Newark"),), "cube_only", 400, 40)),
        (b, Group("c2", (("region", "Camden"),), "cube_only", 30, 3)),
    ]
    body = render_review_issue("Registrar", [_run(applied=Applied(quiet=quiet))])
    assert "- Q1. `region` = `Newark, <redacted>` in c1, c2" in body
    assert "Camden" not in body.split("## Proposed approach")[0]


def test_decisions_with_different_reasons_stay_apart():
    a, g = _left("tardy-roster")
    other = Decision("other", "absences-roster", "domain_owner", "A different question?",
                     {"column": "dashboard_filter", "values": ["enroll_status"]})  # fmt: skip
    quiet = [(a, g), (other, _left("absences-roster")[1])]
    body = render_review_issue("Registrar", [_run(applied=Applied(quiet=quiet))])
    assert (
        sum(
            re.match(r"- Q[12]\. `dashboard_filter`", x) is not None
            for x in body.splitlines()
        )
        == 2
    )


def test_review_issue_merges_missing_fields_and_formula_differences_on_a_reason():
    reason = "Cube has no student filters for these."
    gaps = [
        (Decision(f"g-{f}", "", "domain_owner", reason, missing_filter=f),
         Gap("filter", f, ("Roster",), ("tardy-roster",)))
        for f in ("Gender", "Ethnicity")
    ]  # fmt: skip
    cells = [
        (_formula(f"c-{c}", c, "Codes differ?"), _formula_diff(c, 30))
        for c in ("tardy-roster", "oss-roster")
    ]  # fmt: skip
    run = _run(applied=Applied(quiet_gaps=gaps, quiet_cells=cells))
    body = render_review_issue("Registrar", [run])
    assert (
        "- Q2. `Gender`, `Ethnicity` on `Roster` in `enrollment_view`: sheet filters "
        "Cube has no member for. Reason: " + reason
    ) in body
    assert (
        f"- Q1. `tardy-roster`, `oss-roster` in `enrollment_view`: 60 {FORMULA_ASK} "
        "Reason: Codes differ?"
    ) in body
    assert "owns the rule behind 2 questions" in body


def test_a_school_year_is_a_reviewed_value():
    d = Decision("yoy", "board", "domain_owner", "Newark's AY2026 ADA reads lower",
                 {"column": "regions_region_name", "values": ["Newark"]})  # fmt: skip
    g = Group("board", (("regions_region_name", "Newark"), ("dates_academic_year", "2026")),
              "value_differs", 400, 40)  # fmt: skip
    body = render_review_issue("Registrar", [_run(applied=Applied(quiet=[(d, g)]))])
    assert "Reason: Newark's AY2026 ADA reads lower." in body


def test_merged_comparisons_never_add_up_to_unmask_a_value():
    # 3 students in each of 4 comparisons are the same 3 students, not 12.
    quiet = [_left(c, students=3) for c in ("a", "b", "c", "d")]
    body = render_review_issue("Registrar", [_run(applied=Applied(quiet=quiet))])
    line = next(x for x in body.splitlines() if LEFT in x)
    assert "`dashboard_filter` = `<redacted>`" in line
    assert "at least <10 students in one comparison" in line


def test_groups_of_one_value_never_add_up_to_unmask_it():
    # 2 groups of 6 in one comparison can be the same 6 students (a student
    # with rows in 2 buckets), not 12.
    d, g = _left("tardy-roster", students=6)
    other = Group("tardy-roster", g.dims, "cube_only", 60, 6)
    quiet = [(d, g), (d, other)]
    body = render_review_issue("Registrar", [_run(applied=Applied(quiet=quiet))])
    line = next(x for x in body.splitlines() if LEFT in x)
    assert "`dashboard_filter` = `<redacted>`" in line
    assert "at least <10 students." in line


OOD = "Board YOY leaves out out-of-district students"


def test_one_reason_across_decision_kinds_is_one_bullet():
    rows = Decision("ood-rows", "board", "domain_owner", OOD,
                    {"column": "region", "values": ["Newark"]})  # fmt: skip
    cells = _formula("ood-cells", "board", OOD)
    run = _run(
        applied=Applied(
            quiet=[
                (rows, Group("board", (("region", "Newark"),), "cube_only", 400, 40))
            ],
            quiet_cells=[(cells, _formula_diff("board", 3))],
        )
    )
    body = render_review_issue("Registrar", [run])
    bullets = [x for x in body.splitlines() if OOD in x]
    assert bullets == [
        "- Q1. `region` = `Newark` in board of `enrollment_view` (cube_only): 1 row group, "
        f"400 rows, 40 students; `board` in `enrollment_view`: <10 {FORMULA_ASK} "
        "Reason: " + OOD + "."
    ]
    assert "owns the rule behind 1 question" in body


def test_one_reason_across_files_is_one_bullet():
    reason = "Cube has no enrollment status filter"

    def run_for(view):
        d = Decision(f"{view}-enroll", "", "domain_owner", reason,
                     missing_filter="Enroll Status")  # fmt: skip
        g = Gap("filter", "Enroll Status", ("Roster",), ("c",))
        r = _run(view=view, applied=Applied(quiet_gaps=[(d, g)]))
        return r

    body = render_review_issue(
        "Registrar", [run_for("daily_view"), run_for("periods_view")]
    )
    bullets = [x for x in body.splitlines() if reason in x]
    assert bullets == [
        "- Q1. `Enroll Status` on `Roster` in `daily_view`: a sheet filter Cube has no "
        "member for; `Enroll Status` on `Roster` in `periods_view`: a sheet filter "
        "Cube has no member for. Reason: " + reason + "."
    ]
    fold = body.split("<summary>For Claude</summary>", 1)[1]
    assert "`daily_view-enroll`" in fold and "`periods_view-enroll`" in fold


def test_review_footnote_names_students_and_staff():
    body = render_review_issue("Registrar", [_run()])
    assert (
        "Counts under 10 show as `<10`, and identifiers of students and staff "
        "are hidden." in body
    )


def test_review_issue_ends_with_fenced_json_in_details():
    run = _run(
        applied=Applied(quiet=[(_decision(), _run().applied.quiet[0][1])]),
        diff_cells=[
            {
                "comparison": "enrollment",
                "cut": "{}",
                "key": "a",
                "dims": [["regions_region_name", "Newark"]],
                "dashboard": 40.0,
                "cube": 52.0,
                "n_students": 40,
            }
        ],
        cell_sql={"enrollment": {"{}": ["SELECT 'dash' AS d", "SELECT 'cube' AS c"]}},
        cell_sql_usd={"enrollment": {"{}": [0.01, 0.02]}},
    )
    cfg = ViewConfig(
        view="enrollment_view",
        fact="d.t",
        comparisons=[
            Comparison(
                id="enrollment",
                measure="enrolled",
                dims=[ColumnPair("Region", "regions_region_name")],
            )
        ],
    )
    questions = questions_json([run], [cfg], {}, {}, START)

    body = render_review_issue("Registrar", [run], None, questions)

    tail = re.search(
        r"<details>\n<summary>Questions for Claude \(JSON\)</summary>\n\n"
        r"```json\n(.*)\n```\n\n</details>\n*\Z",
        body,
        re.DOTALL,
    )
    assert tail and json.loads(tail.group(1)) == questions
    check = questions[0]["hand_checks"][0]
    markdown = body[: tail.start()]
    for sql in (check["dashboard_sql"], check["cube_sql"]):
        block = markdown[: markdown.index(sql)].rsplit("<details>", 1)[1]
        assert "</details>" not in block and "<summary>" in block
    assert markdown.count("<details>") == 2  # the hand check and For Claude
    assert "\nQ1, `enrollment` in `enrollment_view`, cut `{}`" in markdown
    # A comparison with no sheet or filters named leaves the sheet as it is.
    assert "On the dashboard: leave the sheet's filters as they are." in markdown
    assert "- Q1. `region` = `Newark`" in markdown


def test_suppress_hides_a_lone_small_part_and_its_next_smallest():
    # 25 = 18 + 7: masking 7 alone leaves it as 25 - 18. With both masked,
    # the total gives only their sum, which holds 10 or more.
    assert suppress(25, [18, 7]) == ("25", ["masked", "<10"])


def test_suppress_rules():
    assert suppress(40, [20, 20]) == ("40", ["20", "20"])
    assert suppress(48, [30, 13, 5]) == ("48", ["30", "masked", "<10"])
    assert suppress(15, [9, 6]) == ("masked", ["<10", "<10"])
    assert suppress(5, [5]) == ("<10", ["<10"])
    assert suppress(120, [100, 20]) == ("120", ["100", "20"])


def test_suppress_never_lets_a_sum_pin_the_small_parts():
    # 18 over two `<10` parts is 9 and 9; 48 - 30 leaves 18 for two `<10`
    # parts, the same. A `masked` part, or a hidden total, breaks the pin.
    assert suppress(18, [9, 9]) == ("masked", ["<10", "<10"])
    assert suppress(27, [9, 9, 9]) == ("masked", ["<10", "<10", "<10"])
    assert suppress(48, [30, 9, 9]) == ("48", ["masked", "<10", "<10"])


def test_suppress_masks_until_the_masked_parts_hold_10_together():
    # Two `<10` parts summing to under 10: the total minus the shown parts
    # would give their sum, so the next-smallest part is masked too.
    assert suppress(30, [22, 4, 4]) == ("30", ["masked", "<10", "<10"])
    assert suppress(40, [25, 3, 2]) == ("40", ["masked", "<10", "<10"])
    assert suppress(50, [30, 11, 5, 4]) == ("50", ["30", "masked", "<10", "<10"])
    assert suppress(12, [11, 1]) == ("12", ["masked", "<10"])


def test_a_hidden_value_is_redacted_only_as_a_whole_value():
    from cube_validation.report import _safe_reason

    text = _safe_reason("grade 1 lost 414 rows; see Q1 and 1.5", ["1"])

    assert text == "grade <redacted> lost 414 rows; see Q1 and 1.5"


def _cause_asks(reasons):
    """One cause proven on a comparison per reason, each decided on its own."""
    asks = []
    for n, reason in enumerate(reasons, start=1):
        d = Decision(
            f"cause-{n}", f"cmp-{n}", "domain_owner", reason,
            cause={"side": "dashboard", "label": "sheet filter team"},
            task="#6150",
        )  # fmt: skip
        g = Group(f"cmp-{n}", (("region", "Newark"),), "value_differs", 400, 40)
        asks.append(CauseAsk(d, [g], 40))
    return {"enrollment_view": asks}


def _cause_review(reasons):
    run = _run(applied=Applied())
    causes = _cause_asks(reasons)
    cfg = ViewConfig(view="enrollment_view", fact="d.t", comparisons=[])
    questions = questions_json([run], [cfg], {}, {}, START, causes=causes)
    body = render_review_issue("Registrar", [run], None, questions, causes=causes)
    return body, questions


def test_a_cause_question_lists_every_distinct_reason():
    body, questions = _cause_review(
        ["Team filter was set by hand", "Roster adds late transfers"]
    )

    assert len(questions) == 1
    for text in (body, questions[0]["reason"]):
        assert "Team filter was set by hand" in text
        assert "Roster adds late transfers" in text
    assert questions[0]["reasons"] == [
        "Team filter was set by hand",
        "Roster adds late transfers",
    ]


def test_a_cause_question_with_one_reason_is_unchanged():
    body, questions = _cause_review(["Team filter was set by hand"] * 2)

    assert questions[0]["reason"] == "Team filter was set by hand"
    assert "reasons" not in questions[0]
    assert "Reasons" not in body.split("## Proposed approach")[0]


def test_a_measure_with_an_open_item_reads_differs():
    assert pipeline.verdict({"pass": 3}, 1, 0, 0) == "differs"
    assert pipeline.verdict({"pass": 3}, 0, 0, 0) == "validated"
    assert (
        pipeline.verdict({"pass": 2, "dashboard_filtered": 1}, 0, 0, 0) == "validated"
    )
    assert pipeline.verdict({"pass": 2, "differs": 1}, 0, 0, 0) == "differs"


def test_a_ticker_line_shows_clock_elapsed_step_and_spend(capsys):
    t = report.Ticker(
        lambda: datetime(2026, 11, 14, 15, 4, 5, tzinfo=timezone.utc),
        datetime(2026, 11, 14, 13, 2, 0, tzinfo=timezone.utc),
    )

    line = t.say("sort", "c1", 0.5)

    assert line == "[15:04:05 UTC +2h02m05s] sort c1: $0.50 spent"
    assert capsys.readouterr().out == line + "\n"


def test_a_ticker_under_an_hour_shows_minutes_and_seconds():
    t = report.Ticker(
        lambda: datetime(2026, 11, 14, 13, 9, 7, tzinfo=timezone.utc),
        datetime(2026, 11, 14, 13, 2, 0, tzinfo=timezone.utc),
    )

    assert t.say("compare", "c1", 12.345) == (
        "[13:09:07 UTC +7m07s] compare c1: $12.35 spent"
    )


EARLIER = Build(
    datetime(2026, 10, 24, 6, 0, tzinfo=timezone.utc),
    datetime(2026, 10, 24, 6, 5, tzinfo=timezone.utc),
    "job-0",
)


def test_local_result_names_one_moment_when_every_comparison_shares_it():
    run = _run(moments={"enrollment": Build(START, END, "job-1")})

    text = render_local(run)

    assert "Moment: 2026-10-27 06:00 to 2026-10-27 06:05 UTC, job `job-1`." in text
    assert "Moments:" not in text


def test_local_result_lists_each_comparison_s_moment_when_they_differ():
    run = _run(moments={"enrollment": EARLIER, "withdrawn": Build(START, END, "job-1")})

    text = render_local(run)

    assert "Moment: " not in text
    assert (
        "Moments:\n\n"
        "- enrollment: 2026-10-24 06:00 to 2026-10-24 06:05 UTC\n"
        "- withdrawn: 2026-10-27 06:00 to 2026-10-27 06:05 UTC\n"
    ) in text
    assert run.moment_of("enrollment") == EARLIER
    assert run.moment_of("never-composed") == run.moment


def test_local_result_names_comparisons_with_no_result():
    text = render_local(_run(missing=["seats-check"]))

    assert "Not compared yet: seats-check." in text


def test_review_issue_lists_each_comparison_s_moment():
    shared = render_review_issue(
        "Registrar", [_run(moments={"enrollment": Build(START, END, "job-1")})]
    )
    differ = render_review_issue(
        "Registrar",
        [_run(moments={"enrollment": EARLIER, "withdrawn": Build(START, END, "j")})],
    )

    assert "Moment: 2026-10-27 06:00 to 2026-10-27 06:05 UTC." in shared
    assert (
        "Moments:\n\n"
        "- enrollment: 2026-10-24 06:00 to 2026-10-24 06:05 UTC\n"
        "- withdrawn: 2026-10-27 06:00 to 2026-10-27 06:05 UTC"
    ) in differ


# --- still with the analyst --------------------------------------------------

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import sort  # noqa: E402


def _left_in_investigate(run, evidence):
    """Each of `compare`'s open row groups as a triage item still in `investigate`,
    its stub holding the group's real values as `triage.json` does."""
    return {
        "items": [
            {
                **dataclasses.asdict(item),
                "suggestion": "investigate",
                "evidence": [evidence],
                "evidence_posted": [evidence],
                "candidates": [],
                "cause": None,
                "proof": None,
            }
            for item in sort.open_items(run)
            if item.kind == "group"
        ]
    }


def _still(run, loaded, waiting=None):
    return report.still_with_analyst(sort.unsettled(run, loaded), waiting or {})


def _detail(run, loaded):
    """The per-item file's lines that list items (`- `)."""
    text = report.unsettled_detail(sort.unsettled(run, loaded), "enrollment_view")
    return [line[2:] for line in text.splitlines() if line.startswith("- ")]


def _open(comparison, what, rows=None, cells=None, item=None, lead=""):
    return report.Unsettled(
        "v", comparison, item or f"{comparison}:{what}:{rows or cells}", what,
        rows=rows, cells=cells, lead=lead,
    )  # fmt: skip


SPREAD = [
    _open("c1", "value_differs", rows=40, item="c1:a"),
    _open("c1", "value_differs", rows=12, item="c1:b"),
    _open("c1", "value_differs", rows=3, item="c1:c"),
    _open("c1", "cube_only", rows=5, item="c1:d"),
    _open("c2", "value", cells=30, item="c2:cells"),
    _open("c2", "group", item="c2:gone"),
]


def test_still_with_the_analyst_counts_open_items_per_comparison_and_bucket():
    lines = report.still_with_analyst(SPREAD, {"v": {"c3": "never compared"}})

    # The total and its parts are masked together (`suppress`), so the file's
    # listed counts never give away the small ones.
    assert lines == [
        "`c1` in `v` (value_differs): <10 open items, 55 rows",
        "`c1` in `v` (cube_only): <10 open items, <10 rows",
        "`c2` in `v` (value): <10 open items, 30 cells",
        "`c2` in `v` (group): <10 open items",
        "`c3` in `v`: never compared",
    ]


def test_unsettled_detail_lists_items_of_10_or_more_and_counts_the_rest():
    text = report.unsettled_detail(SPREAD, "v")

    assert text.startswith("# Still with the analyst: `v`\n\n")
    assert (
        "## `c1` in `v` (value_differs)\n\n"
        "- `c1:a`, 40 rows; no lead yet\n"
        "- `c1:b`, masked rows; no lead yet\n"
        "- Fewer than 10 more items, each under 10 rows or cells, are not listed.\n"
    ) in text
    assert (
        "## `c1` in `v` (cube_only)\n\n"
        "- Fewer than 10 more items, each under 10 rows or cells, are not listed.\n"
    ) in text
    assert "- `c2:cells`, 30 cells; no lead yet\n" in text
    assert "- `c2:gone`; no lead yet\n" in text
    assert "c1:c" not in text and "c1:d" not in text
    assert "3 rows" not in text and "5 rows" not in text and "12" not in text


def test_a_review_with_over_1000_open_groups_stays_under_the_cap():
    items = [
        _open(f"c{i % 4}", ("cube_only", "dashboard_only")[i % 2], rows=i % 25 + 1,
              item=f"c{i % 4}:region=<redacted>:{i}",
              lead="lead: relaxing main: x = 1 brings back <10 of 40 rows")
        for i in range(2_600)
    ]  # fmt: skip
    run = _run()

    body = render_review_issue(
        "Registrar", [run], still=report.still_with_analyst(items, {}),
        still_link="https://github.com/o/r/blob/abc/v-still-with-analyst.md",
    )  # fmt: skip

    assert len(body) <= report.BODY_WARN_CHARS
    section = body.split("## Still with the analyst\n", 1)[1].split("Also decided")[0]
    assert "[v-still-with-analyst.md](https://github.com/o/r/blob/abc/" in section
    assert "`c0` in `v` (cube_only): 650 open items, " in section
    detail = report.unsettled_detail(items, "v")
    listed = [line for line in detail.splitlines() if line.startswith("- `")]
    assert listed and all(", <10 rows" not in line for line in listed)
    assert len(listed) < len(items)


@pytest.mark.parametrize("small", [1, 3, 9])
def test_the_issue_and_the_file_never_give_away_the_small_items_by_subtraction(
    small,
):
    items = [
        _open("c1", "cube_only", rows=20 + i, item=f"c1:big{i}") for i in range(12)
    ]
    items += [_open("c1", "cube_only", rows=1 + i, item=f"c1:small{i}")
              for i in range(small)]  # fmt: skip
    run = _run()

    body = render_review_issue(
        "Registrar", [run], still=report.still_with_analyst(items, {}),
        still_link="https://github.com/o/r/blob/abc/v-still-with-analyst.md",
    )  # fmt: skip
    detail = report.unsettled_detail(items, "v")

    (line,) = [x for x in body.splitlines() if x.startswith("- `c1` in `v`")]
    head = re.match(r"- `c1` in `v` \(cube_only\): (\S+) open items, (\S+) rows", line)
    assert head is not None
    count, rows = head[1], head[2]
    listed = [x for x in detail.splitlines() if x.startswith("- `c1:")]
    assert len(listed) == 12 and not any("small" in x for x in listed)
    # The issue's item count is no exact total a reader could subtract the
    # listed items from, and the file states no count of the small ones.
    assert not count.isdigit()
    stated = re.findall(r"\b(\d+) items\b", detail)
    assert all(int(n) >= 10 for n in stated)
    assert f" {small} items" not in body + detail
    # The rows: the total less the listed exact counts leaves a masked part.
    exact = [int(m) for m in re.findall(r", (\d+) rows;", detail)]
    if rows.isdigit():
        assert re.search(r", masked rows;", detail)
        assert int(rows) - sum(exact) != sum(1 + i for i in range(small))


def test_an_exact_count_of_small_items_is_stated_once_it_is_10_or_more():
    items = [_open("c1", "cube_only", rows=20, item=f"c1:big{i}") for i in range(3)]
    items += [_open("c1", "cube_only", rows=2, item=f"c1:s{i}") for i in range(11)]

    (line,) = report.still_with_analyst(items, {})
    detail = report.unsettled_detail(items, "v")

    assert line.startswith("`c1` in `v` (cube_only): 14 open items, ")
    assert "- Under 10 rows or cells each, not listed: 11 items.\n" in detail


def test_still_with_the_analyst_lists_formulas_not_compared_masked():
    lines = report.still_with_analyst(
        [], {}, {"v": {"c1": {"no rows both sides hold": 3}}}
    )

    assert lines == [
        "`c1` in `v`: formulas not compared: no rows both sides hold; "
        "<10 cells closed by coverage only"
    ]


def test_still_with_the_analyst_sorts_formulas_not_compared():
    lines = report.still_with_analyst(
        [], {}, {"v": {"c2": {"b": 12, "a": 1}, "c1": {"z": 10}}}
    )

    assert [line.split(":")[0] for line in lines] == ["`c1` in `v`"] + [
        "`c2` in `v`"
    ] * 2
    assert lines[1].endswith("a; <10 cells closed by coverage only")
    assert lines[2].endswith("b; 12 cells closed by coverage only")


def test_formulas_not_compared_reads_the_key_or_nothing():
    assert sort.formulas_not_compared({}) == {}
    assert sort.formulas_not_compared({"formulas_not_compared": "x"}) == {}
    assert (
        sort.formulas_not_compared({"formulas_not_compared": {"c": {"r": "x"}}}) == {}
    )
    loaded = {"formulas_not_compared": {"c": {"r": 2}}}
    assert sort.formulas_not_compared(loaded) == {"c": {"r": 2}}
    for n in (0, -3):
        held = {"formulas_not_compared": {"c": {"r": n}, "d": {"r": 2}}}
        assert sort.formulas_not_compared(held) == {"d": {"r": 2}}, n


def test_still_with_the_analyst_redacts_a_long_digit_run_in_a_reason():
    lines = report.still_with_analyst(
        [], {}, {"v": {"c1": {"dry run failed for student 1234567": 12}}}
    )

    assert lines == [
        "`c1` in `v`: formulas not compared: dry run failed for student "
        "<redacted>; 12 cells closed by coverage only"
    ]


def test_formula_checked_tells_an_empty_key_from_a_missing_one():
    # Empty: the check left nothing uncompared. Missing: no check ran.
    # Malformed: fail closed, as if none ran.
    assert sort.formula_checked({"formulas_not_compared": {}})
    assert not sort.formula_checked({})
    assert not sort.formula_checked({"formulas_not_compared": "x"})


def test_review_posts_ready_questions_and_lists_unsettled_items():
    run = _run()
    lead = "lead: relaxing main: school_id IN (1, 2) brings back 30 of 40 rows"
    still = _still(
        run, _left_in_investigate(run, lead), {run.view: {"seats": "never compared"}}
    )

    body = render_review_issue("Registrar", [run], still=still)

    head, section = body.split("## Still with the analyst\n", 1)
    assert "Q1. " in head
    section = section.split("Also decided")[0]
    assert "not explained yet" in section and "comment" in section
    assert (
        "- `enrollment` in `enrollment_view` (value_differs): <10 open items, 40 rows\n"
    ) in section
    assert "school_id" not in body
    assert "- `seats` in `enrollment_view`: never compared" in section
    assert body.index("## Still with the analyst") < body.index("Also decided")
    assert "SELECT" not in section
    assert _detail(run, _left_in_investigate(run, lead)) == [
        "`enrollment:grade_level=9`, 40 rows; lead: relaxing a step in main brings "
        "back 30 of 40 rows"
    ]


def test_unsettled_counts_under_10_are_masked():
    small = Group("enrollment", (("region", "Paterson"),), "cube_only", 7, 3)
    run = _run(applied=Applied(open=[small]))

    loaded = _left_in_investigate(run, "not traced (`sort --no-trace`)")

    (line,) = _still(run, loaded)
    assert (
        line
        == "`enrollment` in `enrollment_view` (cube_only): <10 open items, <10 rows"
    )
    assert _detail(run, loaded) == [
        "Fewer than 10 more items, each under 10 rows or cells, are not listed."
    ]


def test_unsettled_cells_and_reasons_are_posted_without_their_detail():
    diff = CellDiff("enrollment", {"differs": 4, "cube_blank": 2})
    run = _run(applied=Applied(open_cells=[diff]))
    loaded = {
        "items": [
            {
                **dataclasses.asdict(item),
                "suggestion": "investigate",
                "evidence": ["no description or ai_context answers it"],
            }
            for item in sort.open_items(run)
        ]
    }
    waiting = {
        run.view: {"seats": "its SQL cannot be built today: SELECT x FROM t_12345"}
    }

    still = _still(run, loaded, waiting)

    assert still == [
        "`enrollment` in `enrollment_view` (cells): <10 open items, <10 cells",
        "`seats` in `enrollment_view`: its SQL cannot be built today",
    ]


def test_local_result_names_the_comparisons_skipped():
    text = render_local(
        _run(
            skipped=[
                {
                    "comparison": "seats",
                    "why": "no rebuild check; run `rebuild-sheet` first",
                }
            ]
        )
    )

    assert (
        "Skipped this run, each keeping its latest result: seats (no rebuild "
        "check; run "
        "`rebuild-sheet` first)."
    ) in text


def test_a_posted_lead_names_each_step_s_scope_never_its_sql():
    run = _run()
    lead = (
        "lead: relaxing enrolled: x / 2 > 1 / kipptaf_int.int_e/main: INNER JOIN "
        "t AS t ON a = b brings back <10 of 40 rows"
    )

    (line,) = _detail(run, _left_in_investigate(run, lead))

    assert line.endswith(
        "; lead: relaxing a step in enrolled, kipptaf_int.int_e/main brings back "
        "<10 of 40 rows"
    )
    assert "JOIN" not in line and "x / 2" not in line


def test_an_expired_hand_check_says_to_compare_every_comparison():
    # Changed data alone is not stale: a plain `compare` would compare nothing.
    check = {
        "view": "v", "comparison": "c", "cut": "{}", "dims": [],
        "dashboard": "1", "cube": "2", "dashboard_sql": "S", "cube_sql": "T",
        "dashboard_usd": 0.01, "cube_usd": 0.01, "expires": "2026-11-06",
        "expired": True, "workbook": "w", "sheet": "s", "filters": {},
        "mixed": False,
    }  # fmt: skip
    text = "\n".join(report._hand_check_lines("Q1", check))
    assert "re-run `compare --all` for a fresh moment" in text


def test_a_bigquery_skip_posts_its_fixed_words_and_no_message():
    from google.api_core.exceptions import BadRequest

    exc = BadRequest(
        "No matching signature for value 'Student 12345'",
        errors=[{"reason": "invalidQuery"}],
    )
    exc.job_id = "job_x"

    skip = compare._bigquery_skip("c2", "a query", exc)

    assert report._posted_why(skip.why) == (
        "a query failed in BigQuery (job job_x, invalidQuery); compare it again later"
    )
