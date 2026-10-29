# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.sqlsteps import LABEL_CHARS, Query

# Shaped like the DDI dashboard's rows: CTEs, an INNER JOIN, a LEFT JOIN a later
# WHERE requires, a `module_type` conjunct, a LEFT JOIN nothing needs, a dead
# CTE, and a UNION branch whose student column is NULL.
DDI = """
WITH student_week AS (
  SELECT co.*, cw.week_start_monday, cw.week_end_sunday
  FROM `teamster-332318.kipptaf_extracts.enrollments` AS co
  INNER JOIN `teamster-332318.kipptaf_students.calendar_week` AS cw
    ON co.academic_year = cw.academic_year AND co.schoolid = cw.schoolid
),
responses AS (
  SELECT co.student_number, r.assessment_id, r.response_type, sd.standard_domain
  FROM student_week AS co
  LEFT JOIN `teamster-332318.kipptaf_assessments.response_rollup` AS r
    ON co.student_number = r.student_number
    AND r.administered_at BETWEEN co.week_start_monday AND co.week_end_sunday
  LEFT JOIN `teamster-332318.kipptaf_google_sheets.standard_domains` AS sd
    ON r.response_type_code = sd.standard_code
  WHERE co.is_enrolled_week_end AND r.module_type != 'WPP'
),
walkthroughs AS (
  SELECT o.observer_id
  FROM `teamster-332318.kipptaf_people.observations` AS o
  WHERE o.kind = 'WT'
),
unused AS (SELECT x FROM `teamster-332318.d.unused` WHERE flag)
SELECT student_number, assessment_id, response_type
FROM responses
WHERE response_type IN ('overall')
UNION ALL
SELECT NULL AS student_number, observer_id AS assessment_id, 'wt' AS response_type
FROM walkthroughs
"""
GRAIN = frozenset({"student_number", "assessment_id", "response_type"})


def _query(sql=DDI):
    return Query(sql, GRAIN, "student_number")


def _step(q, text):
    (step,) = [s for s in q.steps("dashboard") if text in s.label]
    return step


def _flat(sql: str) -> str:
    return " ".join(sql.split())


def test_finds_the_steps_that_can_drop_a_row():
    labels = {s.label[:120] for s in _query().steps("dashboard")}

    assert labels == {
        "main: response_type IN ('overall')",
        (
            "student_week: INNER JOIN kipptaf_students.calendar_week AS cw ON "
            "co.academic_year = cw.academic_year AND co.schoolid = cw.schoolid"
        )[:120],
        "responses: co.is_enrolled_week_end",
        "responses: r.module_type <> 'WPP'",
        (
            "responses: LEFT JOIN kipptaf_assessments.response_rollup AS r ON "
            "co.student_number = r.student_number AND r.administered_at BETWEEN "
            "co.week_start_monday AND co.week_end_sunday"
        )[:120],
    }


def test_step_ids_name_side_scope_and_number():
    ids = [s.id for s in _query().steps("dashboard")]

    assert len(ids) == len(set(ids))
    assert "dashboard:responses:1" in ids and "dashboard:main:1" in ids
    assert all(i.split(":")[0] == "dashboard" for i in ids)
    prefixed = _query().steps("cube", "fct_scores")
    assert all(s.id.startswith("cube:fct_scores/") for s in prefixed)
    assert all(s.label.startswith("fct_scores/") for s in prefixed)


def test_prunes_steps_that_cannot_change_the_output_keys():
    labels = " ".join(s.label for s in _query().steps("dashboard"))

    # A dead CTE, a branch with no student, a LEFT JOIN nothing needs.
    assert "flag" not in labels
    assert "o.kind" not in labels
    assert "standard_domains" not in labels


def test_a_conjunct_on_a_root_column_becomes_true():
    q = _query()

    out = _flat(q.relaxed(_step(q, "is_enrolled_week_end")))

    assert "WHERE TRUE AND r.module_type <> 'WPP'" in out


def test_a_conjunct_on_a_left_joined_table_holds_only_where_that_table_is_present():
    q = _query()

    out = _flat(q.relaxed(_step(q, "module_type")))

    assert "(r.module_type <> 'WPP') OR NOT r.student_number IS NULL" in out


def test_a_required_left_join_keeps_only_rows_its_table_misses():
    q = _query()

    out = _flat(q.relaxed(_step(q, "LEFT JOIN kipptaf_assessments")))

    assert "(r.module_type <> 'WPP') OR (r.student_number IS NULL)" in out
    assert "WHERE co.is_enrolled_week_end AND" in out


def test_an_inner_join_becomes_a_left_join():
    q = _query()

    out = _flat(q.relaxed(_step(q, "INNER JOIN")))

    assert "LEFT JOIN `teamster-332318.kipptaf_students.calendar_week` AS cw" in out
    assert "INNER JOIN" not in out
    # No other step moves.
    assert "WHERE co.is_enrolled_week_end AND r.module_type <> 'WPP'" in out


CHAINED = """
SELECT b.student AS student, f.score AS score
FROM `teamster-332318.marts.fct` AS f
LEFT JOIN `teamster-332318.marts.sections` AS a ON a.k = f.section_key
LEFT JOIN `teamster-332318.marts.enrollments` AS b ON b.k = a.enrollment_key
WHERE b.school IN ('X', 'Y')
"""


def test_chained_left_joins_split_rows_by_the_first_missing_table():
    q = Query(CHAINED, frozenset({"student", "score"}), "student")
    by_label = {s.label.split(" ON ")[0]: s for s in q.steps("cube")}

    where = _flat(q.relaxed(by_label["main: b.school IN ('X', 'Y')"]))
    first = _flat(q.relaxed(by_label["main: LEFT JOIN marts.sections AS a"]))
    second = _flat(q.relaxed(by_label["main: LEFT JOIN marts.enrollments AS b"]))

    assert "(b.school IN ('X', 'Y')) OR (NOT a.k IS NULL AND NOT b.k IS NULL)" in where
    assert "(b.school IN ('X', 'Y')) OR (a.k IS NULL)" in first
    assert "(b.school IN ('X', 'Y')) OR (b.k IS NULL AND NOT a.k IS NULL)" in second


RESOLVER = """
WITH candidates AS (
  SELECT s.student, s.score_id, ce.section
  FROM `teamster-332318.a.anchors` AS s
  INNER JOIN `teamster-332318.a.course_enrollments` AS ce
    ON s.student = ce.student AND s.anchor_date < ce.left_date AND ce.dcid IS NOT NULL
),
ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY score_id ORDER BY section) AS rn
  FROM candidates
)
SELECT student, score_id FROM ranked WHERE rn = 1
"""


def test_an_inner_join_on_filter_is_a_step_and_its_key_is_not():
    q = Query(RESOLVER, frozenset({"student", "score_id"}), "student")
    labels = {s.label for s in q.steps("cube")}

    assert "candidates: s.anchor_date < ce.left_date (ON ce)" in labels
    assert "candidates: NOT ce.dcid IS NULL (ON ce)" in labels
    assert not any("s.student = ce.student (ON" in label for label in labels)
    step = next(s for s in q.steps("cube") if "left_date (ON" in s.label)
    out = _flat(q.relaxed(step))
    assert "ON s.student = ce.student AND TRUE AND NOT ce.dcid IS NULL" in out


def test_having_and_qualify_conjuncts_are_steps():
    sql = (
        "SELECT student, COUNT(*) AS n FROM `teamster-332318.d.t` "
        "GROUP BY student HAVING COUNT(*) > 1 QUALIFY ROW_NUMBER() OVER () = 1"
    )
    q = Query(sql, frozenset({"student"}), "student")

    labels = [s.label for s in q.steps("cube")]

    assert "main: HAVING COUNT(*) > 1" in labels
    assert "main: QUALIFY ROW_NUMBER() OVER () = 1" in labels
    having = next(s for s in q.steps("cube") if "HAVING" in s.label)
    assert "HAVING TRUE" in q.relaxed(having)


def test_labels_drop_the_moment_and_comments_and_stay_short():
    sql = (
        "SELECT t.student FROM `teamster-332318.d.t` AS t "
        "FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-28 21:34:41+00:00' "
        "INNER JOIN `teamster-332318.d.u` AS u FOR SYSTEM_TIME AS OF "
        "TIMESTAMP '2026-10-28 21:34:41+00:00' ON t.k = u.k "
        "WHERE t.flag /* why */ AND t.name IN ("
        + ", ".join(f"'{'x' * 20}{i}'" for i in range(20))
        + ")"
    )
    q = Query(sql, frozenset({"student"}), "student")

    labels = [s.label for s in q.steps("cube")]

    assert "main: INNER JOIN d.u AS u ON t.k = u.k" in labels
    assert "main: t.flag" in labels
    assert not any("2026" in label or "why" in label for label in labels)
    assert all(len(label) <= LABEL_CHARS for label in labels)


def test_tables_lists_the_live_base_tables_with_the_columns_read():
    tables = {(t.dataset, t.name): t.wanted for t in _query().tables()}

    assert set(tables) == {
        ("kipptaf_extracts", "enrollments"),
        ("kipptaf_students", "calendar_week"),
        ("kipptaf_assessments", "response_rollup"),
    }
    assert {"student_number", "assessment_id", "module_type"} <= tables[
        ("kipptaf_assessments", "response_rollup")
    ]


def test_inline_reads_a_table_as_a_subquery():
    q = Query(CHAINED, frozenset({"student", "score"}), "student")

    out = _flat(q.inline({("marts", "fct"): "SELECT 1 AS score"}))

    assert "FROM (SELECT 1 AS score) AS f" in out
    assert "marts.fct" not in out


def test_relaxed_all_neutralizes_every_step_at_once():
    q = _query()

    out = _flat(q.relaxed_all({("kipptaf_extracts", "enrollments"): "SELECT 1 AS x"}))

    assert "INNER JOIN" not in out
    assert "module_type" not in out and "is_enrolled_week_end" not in out
    assert "(SELECT 1 AS x) AS co" in out
    # Pruned steps stay as they were.
    assert "o.kind = 'WT'" in out
