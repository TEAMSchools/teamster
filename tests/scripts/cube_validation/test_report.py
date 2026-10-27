from datetime import datetime, timezone

from cube_validation.checks import Finding
from cube_validation.compare import Group
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
    quiet_group = Group("enrollment", "region", "Newark", "value_differs", 40, 12)
    id_group = Group("enrollment", "student_number", "123456", "cube_only", 2, 2)
    other_group = Group("enrollment", "region", "Camden", "value_differs", 5, 5)
    open_group = Group("enrollment", "grade_level", "9", "value_differs", 40, 38)
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
        {"column": group.column, "values": [group.value]},
    )
    run = _run(applied=Applied(quiet=[(d, group)]))
    if findings is not None:
        run.findings = findings
    if measures is not None:
        run.measures = measures
    return render_review_issue("Registrar", [run])


def test_review_issue_bullets_stay_on_one_line():
    g = Group("enrollment", "region", "New\nark", "value_differs", 40, 12)
    body = _issue_with(g, reason="line one\n  line two\n\nline three")
    bullets = [x for x in body.splitlines() if x.startswith("- ")]
    assert bullets and all(
        "Reason: line one line two line three" in b for b in bullets[:1]
    )
    assert "line two" in body and "\n  line two" not in body
    assert "- `region` = `New ark`" in body


def test_identifier_like_columns_redacted():
    for col in (
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
    ):
        g = Group("enrollment", col, "SECRETVAL", "cube_only", 50, 50)
        assert "SECRETVAL" not in _issue_with(g)


def test_small_group_on_harmless_column_redacted():
    small = Group("enrollment", "grade_level", "9", "cube_only", 50, 9)
    big = Group("enrollment", "grade_level", "9", "cube_only", 50, 10)
    assert "`grade_level` = `<redacted>`" in _issue_with(small)
    assert "`grade_level` = `9`" in _issue_with(big)


def test_reason_is_sanitized():
    g = Group("enrollment", "region", "Newark", "value_differs", 40, 12)
    body = _issue_with(g, reason="Student 123456 moved to Newark.")
    assert "123456" not in body
    assert "Reason: Student <redacted> moved to <redacted>." in body


def test_reason_with_unquoted_numeric_values():
    g = Group("enrollment", "grade_level", "9", "value_differs", 40, 12)
    d = Decision(
        "dx", "enrollment", "domain_owner", "Grade 9 is split",
        {"column": "grade_level", "values": [9]},
    )  # fmt: skip
    body = render_review_issue("Registrar", [_run(applied=Applied(quiet=[(d, g)]))])
    assert "Reason: Grade <redacted> is split" in body


def test_separated_ids_in_reason_redacted():
    g = Group("enrollment", "region", "Newark", "value_differs", 40, 12)
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
    g = Group("enrollment", "region", "Newark", "value_differs", 40, 12)
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
