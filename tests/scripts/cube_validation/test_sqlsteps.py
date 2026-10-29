import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.sqlsteps import LABEL_CHARS, Query, carry

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

    # Parenthesized: an OR spliced into an AND chain must not swallow it.
    assert (
        "WHERE co.is_enrolled_week_end AND "
        "((r.module_type <> 'WPP') OR NOT r.student_number IS NULL)"
    ) in out


def test_a_required_left_join_keeps_only_rows_its_table_misses():
    q = _query()

    out = _flat(q.relaxed(_step(q, "LEFT JOIN kipptaf_assessments")))

    assert (
        "WHERE co.is_enrolled_week_end AND "
        "((r.module_type <> 'WPP') OR (r.student_number IS NULL))"
    ) in out


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
    # `rn = 1` on a ROW_NUMBER column picks a row: never a step.
    assert not any("rn = 1" in label for label in labels)


def _resolver_tables(duck):
    duck.table(
        "anchors",
        "student BIGINT, score_id VARCHAR, anchor_date DATE",
        [(1, "a", "2026-09-01"), (2, "b", "2026-09-01"), (3, "c", "2026-09-01")],
    )
    duck.table(
        "course_enrollments",
        "student BIGINT, section VARCHAR, left_date DATE, dcid BIGINT",
        # 1: section ended before the anchor (fails the date filter only);
        # 2: no section at all (fails the key); 3: matches.
        [(1, "s1", "2026-06-01", 10), (3, "s3", "2027-06-01", 30)],
    )


def _students(duck, sql):
    return sorted(r["student"] for r in duck.rows(sql))


def test_an_inner_join_s_filter_and_its_key_split_the_rows_they_drop(duck):
    _resolver_tables(duck)
    q = Query(RESOLVER, frozenset({"student", "score_id"}), "student")
    by_label = {s.label: s for s in q.steps("cube")}
    join = next(s for s in q.steps("cube") if s.kind == "join")
    date = by_label["candidates: s.anchor_date < ce.left_date (ON ce)"]

    assert _students(duck, q.sql()) == [3]
    # The date filter alone brings back the row whose only failure it is;
    # the join alone brings back the row with no key match, and not the other.
    assert _students(duck, q.relaxed(date)) == [1, 3]
    assert _students(duck, q.relaxed(join)) == [2, 3]


def test_two_steps_of_one_select_neutralize_together(duck):
    duck.table(
        "t", "student BIGINT, ok BOOLEAN, k BIGINT", [(1, False, 9), (2, True, 5)]
    )
    duck.table("u", "k BIGINT, open BOOLEAN", [(5, True)])
    sql = (
        "SELECT t.student FROM `teamster-332318.d.t` AS t "
        "LEFT JOIN `teamster-332318.d.u` AS u ON u.k = t.k "
        "WHERE t.ok AND u.open"
    )
    q = Query(sql, frozenset({"student"}), "student")
    ok, join = (
        next(s for s in q.steps("cube") if s.label == "main: t.ok"),
        next(s for s in q.steps("cube") if s.kind == "join"),
    )

    # Row 1 fails `t.ok` and has no `u` row: neither step alone brings it
    # back, both together do.
    assert _students(duck, q.relaxed(ok)) == [2]
    assert _students(duck, q.relaxed(join)) == [2]
    assert _students(duck, q.relaxed_many([ok, join])) == [1, 2]
    assert _students(duck, q.relaxed_many([join, ok])) == [1, 2]


def test_a_left_join_with_no_key_equality_uses_its_alias_as_presence():
    sql = (
        "SELECT t.student FROM `teamster-332318.d.t` AS t "
        "LEFT JOIN `teamster-332318.d.u` AS u ON t.d BETWEEN u.lo AND u.hi "
        "WHERE u.open"
    )
    q = Query(sql, frozenset({"student"}), "student")
    join = next(s for s in q.steps("cube") if s.kind == "join")
    where = next(s for s in q.steps("cube") if s.kind == "where")

    assert "(u.open) OR (u IS NULL)" in _flat(q.relaxed(join))
    assert "(u.open) OR NOT u IS NULL" in _flat(q.relaxed(where))


def test_steps_under_not_in_or_not_exists_are_left_out():
    sql = (
        "SELECT t.student FROM `teamster-332318.d.t` AS t "
        "WHERE t.student NOT IN (SELECT s FROM `teamster-332318.d.x` WHERE gone) "
        "AND NOT EXISTS (SELECT 1 FROM `teamster-332318.d.y` WHERE closed) "
        "AND t.school IN (SELECT s FROM `teamster-332318.d.z` WHERE open)"
    )
    q = Query(sql, frozenset({"student"}), "student")

    labels = [s.label.split(": ", 1)[1] for s in q.steps("cube")]

    assert "open" in labels
    assert "gone" not in labels and "closed" not in labels


def test_having_is_a_step_and_qualify_is_a_row_pick():
    sql = (
        "SELECT student, COUNT(*) AS n FROM `teamster-332318.d.t` "
        "GROUP BY student HAVING COUNT(*) > 1 QUALIFY ROW_NUMBER() OVER () = 1"
    )
    q = Query(sql, frozenset({"student"}), "student")

    labels = [s.label for s in q.steps("cube")]

    assert labels == ["main: HAVING COUNT(*) > 1"]
    assert "HAVING TRUE" in q.relaxed(q.steps("cube")[0])


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


def test_a_scalar_subquery_s_steps_are_left_alone_and_an_in_list_s_kept():
    # Neutralizing a step inside a scalar subquery can make it return several
    # rows, which BigQuery refuses at run time.
    sql = (
        "SELECT t.student FROM `teamster-332318.d.t` AS t "
        "WHERE t.year = (SELECT MAX(y) FROM `teamster-332318.d.years` WHERE live) "
        "AND t.school IN (SELECT s FROM `teamster-332318.d.schools` WHERE open)"
    )
    q = Query(sql, frozenset({"student"}), "student")

    labels = [s.label for s in q.steps("cube")]

    assert not any(label.endswith(": live") for label in labels)
    assert any(label.endswith(": open") for label in labels)
    step = next(s for s in q.steps("cube") if s.label.endswith(": open"))
    assert "WHERE live" in q.relaxed(step) and "WHERE TRUE" in q.relaxed(step)


def test_steps_in_a_nested_select_neutralize_with_the_outer_one():
    # N6: the IN subquery's step sits inside the outer conjunct.
    # The outer conjunct reads a LEFT-joined table, so neutralizing it keeps
    # a copy of the conjunct, subquery and all.
    sql = (
        "SELECT t.student FROM `teamster-332318.d.t` AS t "
        "LEFT JOIN `teamster-332318.d.u` AS u ON u.k = t.k "
        "WHERE u.school IN (SELECT s FROM `teamster-332318.d.z` WHERE open) "
        "AND t.ok"
    )
    q = Query(sql, frozenset({"student"}), "student")
    outer = next(s for s in q.steps("cube") if "IN (" in s.label)
    inner = next(s for s in q.steps("cube") if s.label.endswith(": open"))

    alone = _flat(q.relaxed(outer))
    both = _flat(q.relaxed_many([outer, inner]))

    assert "WHERE open" in alone
    assert "WHERE open" not in both and "OR NOT u.k IS NULL" in both


def test_the_match_marker_is_a_key_column_never_a_filter_column():
    # N8: `x.status = 'on'` filters; `x.k = t.k` is the key.
    sql = (
        "SELECT t.student FROM `teamster-332318.d.t` AS t "
        "INNER JOIN `teamster-332318.d.x` AS x ON x.status = 'on' AND x.k = t.k"
    )
    q = Query(sql, frozenset({"student"}), "student")
    step = next(s for s in q.steps("cube") if s.kind == "on")

    out = _flat(q.relaxed(step))

    assert "NOT x.k IS NULL" in out and "NOT x.status IS NULL" not in out


def test_row_picks_written_backwards_or_passed_through_a_star_are_found():
    # N9.
    sql = (
        "WITH r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY student ORDER BY d) "
        "AS rn FROM `teamster-332318.d.t`), "
        "s AS (SELECT * FROM r) "
        "SELECT student FROM s WHERE 2 > rn AND 1 >= rn AND ok"
    )
    q = Query(sql, frozenset({"student"}), "student")

    labels = [s.label for s in q.steps("cube")]

    assert labels == ["main: ok"]


def test_relaxed_all_also_drops_row_picks():
    # N2: presence must bring back a row a pick drops.
    sql = (
        "WITH r AS (SELECT student, ROW_NUMBER() OVER (PARTITION BY student "
        "ORDER BY d) AS rn FROM `teamster-332318.d.t`) "
        "SELECT student FROM r WHERE rn = 1 QUALIFY TRUE"
    )
    out = _flat(Query(sql, frozenset({"student"}), "student").relaxed_all())

    assert "rn = 1" not in out


PICK = (
    "WITH f AS (SELECT student, item, d FROM `teamster-332318.d.src` WHERE x), "
    "r AS (SELECT student, item, ROW_NUMBER() OVER "
    "(PARTITION BY student ORDER BY d DESC) AS rn FROM f) "
)


def test_only_a_step_ahead_of_a_pick_is_marked():
    q = Query(
        PICK + "SELECT student, item FROM r WHERE rn = 1 AND item <> 'z'",
        frozenset({"student", "item"}),
        "student",
    )
    before = next(s for s in q.steps("cube") if s.label == "f: x")
    after = next(s for s in q.steps("cube") if "<> 'z'" in s.label)

    sql, marks = q.relaxed_marked([before])

    assert marks == ["__cand0"]
    assert "COUNT(*) OVER (PARTITION BY student) AS __cand0" in sql
    assert q.relaxed_marked([after])[1] == []


def test_a_count_an_aggregate_would_swallow_is_not_carried():
    q = Query(
        PICK + "SELECT student, MAX(item) AS item FROM r WHERE rn = 1 GROUP BY student",
        frozenset({"student", "item"}),
        "student",
    )
    step = next(s for s in q.steps("cube") if s.label == "f: x")

    sql, marks = q.relaxed_marked([step])

    assert carry(sql, marks) is None


# --- fix round 4: the guard fails closed ------------------------------------------

WINDOW = "ROW_NUMBER() OVER (PARTITION BY student ORDER BY d DESC) AS rn"
KEY = frozenset({"student", "item"})


def test_a_step_in_an_in_subquery_of_the_window_s_select_is_marked():
    # N-new-1: the step feeds the pick through the WHERE, not the FROM.
    q = Query(
        f"WITH r AS (SELECT student, item, {WINDOW} FROM `teamster-332318.d.src` "
        "WHERE d IN (SELECT d FROM `teamster-332318.d.days` WHERE z)) "
        "SELECT student, item FROM r WHERE rn = 1",
        KEY,
        "student",
    )
    step = next(s for s in q.steps("cube") if s.label == "r: z")

    assert q.relaxed_marked([step])[1] == ["__cand0"]


UNION_PICKS = (
    f"WITH u AS (SELECT student, item, {WINDOW} FROM `teamster-332318.d.src` WHERE x "
    "UNION ALL SELECT student, item, {rn} FROM `teamster-332318.d.src2` WHERE y) "
    "SELECT student, item FROM u WHERE rn = 1"
)


def test_a_pick_over_a_union_marks_the_branch_a_step_feeds():
    # N-new-2: each branch computes its own rn.
    q = Query(UNION_PICKS.format(rn=WINDOW), KEY, "student")
    x = next(s for s in q.steps("cube") if s.label == "u: x")
    y = next(s for s in q.steps("cube") if s.label == "u: y")

    for_x, marks_x = q.relaxed_marked([x])
    for_y, marks_y = q.relaxed_marked([y])

    assert marks_x == marks_y == ["__cand0"]
    first, second = _flat(for_x).split("UNION ALL")
    assert "__cand0" in first and "__cand0" not in second
    first, second = _flat(for_y).split("UNION ALL")
    assert "__cand0" in second and "__cand0" not in first


def test_a_pick_a_branch_computes_without_a_window_cannot_be_marked():
    # N-new-2: the second branch's rn is a literal, so its candidates cannot
    # be counted; the whole pick is then out of the guard's reach.
    q = Query(UNION_PICKS.format(rn="1 AS rn"), KEY, "student")
    x = next(s for s in q.steps("cube") if s.label == "u: x")

    sql, marks = q.relaxed_marked([x])

    assert marks is None
    assert "__cand" not in sql and sql == q.relaxed(x)


def _set_op(op: str) -> str:
    return (
        f"WITH r AS (SELECT student, item, {WINDOW} FROM `teamster-332318.d.src` "
        f"WHERE x), k AS (SELECT student, item FROM r WHERE rn = 1 {op} "
        "SELECT student, item FROM `teamster-332318.d.excl`) "
        "SELECT student, item FROM k"
    )


@pytest.mark.parametrize(
    "op", ["EXCEPT DISTINCT", "INTERSECT DISTINCT", "UNION DISTINCT"]
)
def test_a_count_is_carried_through_union_all_and_no_other_set_operation(op):
    # N-new-3: a mark on one branch alone changes which rows the others keep.
    for text, carried in ((_set_op(op), False), (_set_op("UNION ALL"), True)):
        q = Query(text, KEY, "student")
        step = next(s for s in q.steps("cube") if s.label == "r: x")
        sql, marks = q.relaxed_marked([step])

        assert marks == ["__cand0"]
        assert (carry(sql, marks) is not None) == carried


def test_a_count_from_a_table_read_twice_is_not_carried():
    # A frame inlined twice: one copy's count says nothing about the other's.
    child = (
        "SELECT student, item, COUNT(*) OVER (PARTITION BY student) AS __cand0 "
        "FROM `teamster-332318.d.src`"
    )
    once = f"SELECT a.student, a.item FROM ({child}) AS a"
    twice = f"{once} JOIN ({child}) AS b ON a.student = b.student"

    assert carry(once, ["__cand0"]) is not None
    assert carry(twice, ["__cand0"]) is None


def test_a_pick_reading_an_inlined_table_is_marked():
    # P-old-1: the pick sits in the frame above the step.
    q = Query(
        f"WITH r AS (SELECT student, item, {WINDOW} FROM `teamster-332318.d.fact3`) "
        "SELECT student, item FROM r WHERE rn = 1",
        KEY,
        "student",
    )
    child = "SELECT student, item, d FROM `teamster-332318.d.raw3` WHERE keep"

    sql, marks = q.inline_marked({("d", "fact3"): child}, 2)

    assert marks == ["__cand2"]
    assert "COUNT(*) OVER (PARTITION BY student) AS __cand2" in _flat(sql)
    assert "WHERE keep" in _flat(sql)
    other = {("d", "other"): child}
    assert q.inline_marked(other, 2) == (q.inline(other), [])
