from datetime import datetime, timezone

from cube_validation.checks import Finding

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.compare import CellDiff, Gap, Group
from cube_validation.config import Decision
from cube_validation.decisions import Applied
from cube_validation.moment import Build
from cube_validation.report import (
    MeasureResult,
    RunResult,
    mask,
    render_local,
    render_review_issue,
    save_local,
)

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
            (_decision(id="d2", column="student_number", values=("123456",)), id_group),
            (_decision(call="deliberate", id="d3"), other_group),
        ],
        reconfirm=[_decision(id="d4")],
        no_longer_needed=[_decision(id="d5")],
    )
    base = dict(
        view="enrollment_view",
        moment=Build(START, END, "job-1"),
        measures=[
            MeasureResult("enrolled", "matches a dashboard", "validated", {"pass": 12}),
            MeasureResult(
                "withdrawn",
                "matches a dashboard",
                "differs",
                {"pass": 10, "differs": 1},
            ),
            MeasureResult(
                "seats", "anchored to a source", "judge the anchor", {"pass": 1}
            ),
            MeasureResult("ratio", "consistent only", "not validated", {}),
            MeasureResult("misc", "none", "not validated", {}),
        ],
        applied=applied,
        findings=[
            Finding("anchor", "seats", "seats vs state", 7.0, 1234.5, False),
            Finding("identity", "ratio", "ratio identity", 1.0, 1.0, True),
        ],
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


def test_consistent_only_measure_reads_not_validated():
    text = render_local(_run())
    assert "not validated (consistent only)" in text
    assert "misc" in text and "(consistent only)" not in text.split("misc")[1]


def test_measure_line_names_open_row_groups():
    measures = [
        MeasureResult("enrolled", "matches a dashboard", "validated", {"pass": 135}, 2),
        MeasureResult("left", "matches a dashboard", "validated", {"pass": 3}, 1),
        MeasureResult("clean", "matches a dashboard", "validated", {"pass": 4}),
    ]
    text = render_local(_run(measures=measures))
    assert (
        "- `enrolled`: matches a dashboard; validated (pass 135); "
        "2 open row groups to triage"
    ) in text
    assert "validated (pass 3); 1 open row group to triage" in text
    assert "- `clean`: matches a dashboard; validated (pass 4)\n" in text


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
        "## Triage",
        "## Decisions",
        "## Sources read live",
        "## Dimensions that changed",
        "## Scopes",
        "## Cuts to prove in the browser",
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
    assert "1234.5" in body
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


def _issue_with(group, reason="ok", findings=None, measures=None):
    d = Decision(
        "dx",
        "enrollment",
        "domain_owner",
        reason,
        {"column": group.dims[0][0], "values": [group.dims[0][1]]},
    )
    run = _run(applied=Applied(quiet=[(d, group)]))
    if findings is not None:
        run.findings = findings
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
    assert "- `region` = `New ark`" in body


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


def test_passing_anchor_not_listed_and_count_masking():
    measures = [
        MeasureResult("count_seats", "anchored to a source", "judge the anchor"),
        MeasureResult("rate", "anchored to a source", "judge the anchor"),
        MeasureResult("fine", "anchored to a source", "judge the anchor"),
    ]
    findings = [
        Finding("anchor", "count_seats", "d", 7.0, 8.0, False),
        Finding("anchor", "rate", "d", 7.0, 8.0, False),
        Finding("anchor", "fine", "d", 1.0, 1.0, True),
    ]
    g = Group("enrollment", (("region", "Newark"),), "value_differs", 40, 12)
    body = _issue_with(g, findings=findings, measures=measures)
    assert (
        "`count_seats` in `enrollment_view`: Cube shows <10, the source shows <10."
        in body
    )
    assert "`rate` in `enrollment_view`: Cube shows 7, the source shows 8." in body
    assert "`fine`" not in body


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
    assert "- `regions_region_name` = `Camden` in enrollment" in body
    assert "SECRETVAL" not in body
    assert "Reason: Camden <redacted> rows" in body


def test_local_result_says_anchors_read_current_data():
    caveat = "Anchors and identities read Cube's data as it is now"
    assert caveat not in render_local(_run(findings=[]))
    findings = [Finding("anchor", "rate", "d", 7.0, 8.0, False)]
    assert caveat in render_local(_run(findings=findings))


GAP_TEAM = Gap("cut", "Team", ("Roster",), ("tardy-roster", "absent-roster"))
GAP_ENROLL = Gap("filter", "Enroll Status", ("Roster",), ("tardy-roster",), True)


def _gap_decision(call="domain_owner"):
    return Decision(
        id="g1", comparison="", call=call, reason="owner decides the cut",
        task="#6150", missing_cut="Team",
    )  # fmt: skip


def test_local_result_lists_missing_cuts_and_filters():
    run = _run(applied=Applied(open_gaps=[GAP_TEAM, GAP_ENROLL]))
    run.gaps_unknown = ["ada: missing cuts and filters unknown; re-prove"]
    text = render_local(run)
    section = text.split("## Missing cuts and filters", 1)[1].split("## ", 1)[0]
    assert (
        "`Team` (cut) on Roster: Cube has no member; tardy-roster, absent-roster"
        in section
    )
    assert (
        "`Enroll Status` (filter, set to chosen values, not All) on Roster" in section
    )
    assert "ada: missing cuts and filters unknown; re-prove" in section


def test_measure_line_counts_open_missing_cuts():
    run = _run()
    run.measures[0].open_gaps = 2
    assert "2 missing cuts or filters to triage" in render_local(run)


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


def test_review_issue_leaves_out_other_missing_cut_calls():
    run = _run(applied=Applied(quiet_gaps=[(_gap_decision("fix_cube"), GAP_TEAM)]))
    assert "`Team`" not in render_review_issue("Registrar", [run])


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
    cuts = text.split("## Cuts to prove in the browser", 1)[1].split("## ", 1)[0]
    assert "ada" not in cuts and "None." in cuts
    proofs = text.split("## Proofs", 1)[1].split("## ", 1)[0]
    assert "ada: last proven 2026-10-27T19:00" in proofs


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
    assert "cell differences to triage in 1 comparison" in text


def test_review_issue_carries_domain_owner_cell_differences():
    d = Decision(
        "cells-1", "enrollment", "domain_owner", "owner picks codes", cells=True
    )
    run = _run(applied=Applied(quiet_cells=[(d, TARDY_DIFF)]))
    body = render_review_issue(
        "Registrar", [run], definitions={"enrollment_view": TARDY_DEFS}
    )
    assert (
        "`enrollment` in `enrollment_view`: 61 cells differ between Cube and the dashboard"
        in body
    )
    assert "Reason: owner picks codes" in body
    assert "Definitions side by side" in body
    # Candidate causes stay local: they can name a cut or a value.
    assert "values differ beyond rounding" not in body


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
    bullets = [x for x in body.splitlines() if x.startswith("- `dashboard_filter`")]
    assert bullets == [
        "- `dashboard_filter` = `enroll_status` in tardy-roster of `enrollment_view` "
        "(dashboard_filtered): 13 row groups, 130 rows, 130 students. "
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
    d = Decision("td", "enrollment", "domain_owner", q, cells=True)
    diff = CellDiff("enrollment", {"differs": 58})
    body = render_review_issue(
        "Registrar", [_run(applied=Applied(quiet_cells=[(d, diff)]))]
    )
    assert f"Reason: {q}\n" in body + "\n" and "?." not in body
    tasked = Decision("td", "enrollment", "domain_owner", q, task="#6200", cells=True)
    body = render_review_issue(
        "Registrar", [_run(applied=Applied(quiet_cells=[(tasked, diff)]))]
    )
    assert f"Reason: {q} Task: #6200" in body


def test_review_issue_counts_questions_and_lists_every_decision():
    cells = Decision(
        "tardy-cells", "tardy-roster", "domain_owner", "codes?", cells=True
    )
    gap = _gap_decision()
    run = _run(
        applied=Applied(
            quiet=_enrolled_only(),
            quiet_cells=[(cells, CellDiff("tardy-roster", {"differs": 58}))],
            quiet_gaps=[(gap, GAP_TEAM)],
        )
    )
    body = render_review_issue("Registrar", [run])
    # 3 decisions, however many groups they cover, plus the 1 anchor finding.
    assert "owns the rule behind 4 questions" in body
    fold = body.split("<summary>For Claude</summary>", 1)[1]
    for decision_id in ("tardy-enrolled", "tardy-cells", "g1"):
        assert f"`{decision_id}`" in fold


def test_a_small_group_hides_its_value_in_the_reason_too():
    d = Decision("newark", "enrollment", "domain_owner", "Some Newark students moved",
                 {"column": "region", "values": ["Newark"]})  # fmt: skip
    g = Group("enrollment", (("region", "Newark"),), "cube_only", 39, 3)
    body = render_review_issue("Registrar", [_run(applied=Applied(quiet=[(d, g)]))])
    assert "- `region` = `<redacted>`" in body
    assert "Reason: Some <redacted> students moved." in body
    assert "Newark" not in body.split("## Proposed approach")[0]
