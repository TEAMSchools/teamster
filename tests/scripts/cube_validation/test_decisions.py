import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.compare import CellDiff, Gap, Group
from cube_validation.config import Decision
from cube_validation.decisions import apply, sql_fingerprint

FP = {"cube": "c1", "dashboard": "d1"}


def _group(value="Newark", comparison_id="enrollment", column="region"):
    return Group(comparison_id, ((column, value),), "value_differs", 3, 3)


def _decision(id="d1", values=("Newark",), fingerprints=None, column="region"):
    return Decision(
        id=id,
        comparison="enrollment",
        call="deliberate",
        reason="known",
        group={"column": column, "values": list(values)},
        fingerprints=dict(FP) if fingerprints is None else fingerprints,
    )


def test_whitespace_and_comment_changes_keep_fingerprint():
    a = "SELECT a, b FROM t WHERE x = 'Keep'"
    b = "select a,   b\n  from t -- note\n where x = 'Keep' /* why */"
    assert sql_fingerprint(a) == sql_fingerprint(b)


def test_comment_markers_inside_literals_are_kept():
    assert sql_fingerprint("select '-- x' as a") != sql_fingerprint("select '' as a")
    assert sql_fingerprint('select "-- x" as a') != sql_fingerprint('select "" as a')
    assert sql_fingerprint("select '/* x */' as a") != sql_fingerprint("select '' as a")


def test_backtick_case_change_changes_fingerprint():
    assert sql_fingerprint("select 1 from `Proj.DS.T`") != sql_fingerprint(
        "select 1 from `proj.ds.t`"
    )


def test_double_quoted_literal_case_change_changes_fingerprint():
    assert sql_fingerprint('select "A" as x') != sql_fingerprint('select "a" as x')


def test_escaped_quote_does_not_end_literal():
    a = "select 'it\\'s -- A' as x from t"
    b = "select 'it\\'s -- a' as x from t"
    assert sql_fingerprint(a) != sql_fingerprint(b)
    # Text after the literal is still normalized.
    assert sql_fingerprint(a) == sql_fingerprint(a.replace("from t", "FROM   T"))


def test_whitespace_inside_literal_is_preserved():
    assert sql_fingerprint("select 'a  b' as x") != sql_fingerprint("select 'a b' as x")


def test_raw_and_triple_quoted_strings_are_protected():
    assert sql_fingerprint("select r'A\\' as x") != sql_fingerprint(
        "select r'a\\' as x"
    )
    assert sql_fingerprint("select '''A\nB''' as x") != sql_fingerprint(
        "select '''a\nB''' as x"
    )
    assert sql_fingerprint('select """A  B""" as x') != sql_fingerprint(
        'select """A B""" as x'
    )


def test_logic_change_changes_fingerprint():
    assert sql_fingerprint("select a from t where x = 'A'") != sql_fingerprint(
        "select a from t where x = 'a'"
    )
    assert sql_fingerprint("select a from t") != sql_fingerprint("select b from t")


def test_matching_decision_quiets_group():
    d, g = _decision(), _group()
    other = _group("Camden")
    applied = apply([d], [g, other], {"enrollment": FP})
    assert applied.quiet == [(d, g)]
    assert applied.open == [other]
    assert applied.reconfirm == []
    assert applied.no_longer_needed == []


def test_unquoted_yaml_number_matches_its_group():
    # YAML reads `values: [9]` as an int; a group's value is always text.
    d = _decision(values=(9, 9.5, None), column="grade_level")
    groups = [
        _group("9", column="grade_level"),
        _group("9.5", column="grade_level"),
        _group("", column="grade_level"),
    ]
    applied = apply([d], groups, {"enrollment": FP})
    assert [g for _, g in applied.quiet] == groups
    assert applied.open == [] and applied.no_longer_needed == []


def test_changed_sql_asks_to_reconfirm():
    d, g = _decision(), _group()
    for changed in ({"cube": "x", "dashboard": "d1"}, {"cube": "c1", "dashboard": "x"}):
        applied = apply([d], [g], {"enrollment": changed})
        assert applied.reconfirm == [d]
        assert applied.open == [g]
        assert applied.quiet == []
        assert applied.no_longer_needed == []


def test_missing_group_marks_no_longer_needed():
    d = _decision()
    applied = apply([d], [_group("Camden")], {"enrollment": FP})
    assert applied.no_longer_needed == [d]
    assert len(applied.open) == 1


def test_some_values_missing_marks_partly_stale():
    d = _decision(values=("Newark", "Camden", "Miami"))
    newark = _group("Newark")

    applied = apply([d], [newark], {"enrollment": FP})

    assert applied.quiet == [(d, newark)]
    assert applied.partly_stale == [(d, ["Camden", "Miami"])]
    assert applied.open == [] and applied.no_longer_needed == []


def test_every_value_matching_is_not_partly_stale():
    d = _decision(values=("Newark", "Camden"))

    applied = apply([d], [_group("Newark"), _group("Camden")], {"enrollment": FP})

    assert applied.partly_stale == []
    assert len(applied.quiet) == 2


def test_two_decisions_claiming_one_group_raise():
    with pytest.raises(ValueError, match="d1.*d2"):
        apply(
            [_decision("d1"), _decision("d2", values=("Newark", "Miami"))],
            [_group()],
            {"enrollment": FP},
        )


def test_column_and_comparison_must_match():
    d = _decision(column="school")
    applied = apply([d], [_group()], {"enrollment": FP})
    assert applied.no_longer_needed == [d]
    assert len(applied.open) == 1


def test_missing_current_fingerprint_reconfirms():
    d, g = _decision(), _group()
    applied = apply([d], [g], {})
    assert applied.reconfirm == [d]
    assert applied.open == [g]
    assert applied.quiet == []


def test_empty_stored_fingerprints_reconfirm():
    d, g = _decision(fingerprints={}), _group()
    applied = apply([d], [g], {})
    assert applied.reconfirm == [d]
    applied = apply([d], [g], {"enrollment": FP})
    assert applied.reconfirm == [d]
    assert applied.open == [g]


def test_decision_missing_one_side_reconfirms():
    d, g = _decision(fingerprints={"cube": "c1"}), _group()
    applied = apply([d], [g], {"enrollment": {"cube": "c1"}})
    assert applied.reconfirm == [d]
    assert applied.open == [g]


def _row(region, grade, comparison_id="enrollment"):
    return Group(
        comparison_id,
        (("region", region), ("grade_level", grade)),
        "value_differs",
        3,
        3,
    )


def test_decision_on_one_column_quiets_whole_rows_of_a_two_dim_comparison():
    groups = [_row("Newark", "2"), _row("Newark", "3"), _row("Camden", "2")]
    applied = apply([_decision()], groups, {"enrollment": FP})
    assert [g for _, g in applied.quiet] == groups[:2]
    assert applied.open == [groups[2]]
    assert applied.partly_stale == []


def test_overlapping_decisions_on_two_dim_rows_raise():
    groups = [_row("Newark", "2")]
    grade = _decision(id="d2", column="grade_level", values=("2",))
    with pytest.raises(ValueError, match="region='Newark', grade_level='2'"):
        apply([_decision(), grade], groups, {"enrollment": FP})


def test_decision_on_a_column_the_rows_lack_is_no_longer_needed():
    applied = apply(
        [_decision(column="school")], [_row("Newark", "2")], {"enrollment": FP}
    )
    assert applied.no_longer_needed and len(applied.open) == 1


TEAM = Gap("cut", "Team", ("Roster",), ("tardy-roster",))
TERM = Gap("filter", "Term", ("Roster",), ("tardy-roster",))


def _gap_decision(id="g1", cut="Team", flt=""):
    return Decision(
        id=id, comparison="", call="fix_cube", reason="no member", task="#1",
        missing_cut=cut, missing_filter=flt,
    )  # fmt: skip


def test_gap_decision_quiets_its_gap_without_fingerprints():
    applied = apply([_gap_decision()], [], {}, gaps=[TEAM, TERM])
    assert applied.quiet_gaps == [(_gap_decision(), TEAM)]
    assert applied.open_gaps == [TERM] and applied.reconfirm == []


def test_gap_decision_matches_kind_and_field():
    # A cut decision does not quiet a filter of the same name.
    term_cut = _gap_decision(cut="Term")
    applied = apply([term_cut], [], {}, gaps=[TERM])
    assert applied.open_gaps == [TERM]
    assert applied.no_longer_needed == [term_cut]


def test_two_decisions_on_one_gap_raise():
    with pytest.raises(ValueError, match="missing cut 'Team'"):
        apply([_gap_decision(), _gap_decision(id="g2")], [], {}, gaps=[TEAM])


def test_filling_in_a_task_keeps_the_decisions_fingerprint():
    from cube_validation.decisions import decisions_fingerprint

    before = Decision("d", "c", "domain_owner", "r", {"column": "x", "values": ["1"]})
    after = Decision(
        "d", "c", "domain_owner", "r", {"column": "x", "values": ["1"]}, task="#6200"
    )
    assert decisions_fingerprint([before]) == decisions_fingerprint([after])
    changed = Decision("d", "c", "deliberate", "r", {"column": "x", "values": ["1"]})
    assert decisions_fingerprint([before]) != decisions_fingerprint([changed])


def _cells_decision(fingerprints=None):
    return Decision(
        id="cells-1", comparison="enrollment", call="domain_owner", reason="r",
        fingerprints=dict(FP) if fingerprints is None else fingerprints, cells=True,
    )  # fmt: skip


DIFF = CellDiff("enrollment", {"differs": 58}, ("58 cells: values differ",))


def test_cells_decision_quiets_its_comparison_cell_differences():
    applied = apply([_cells_decision()], [], {"enrollment": FP}, cell_diffs=[DIFF])
    assert applied.quiet_cells == [(_cells_decision(), DIFF)]
    assert applied.open_cells == []


def test_cells_decision_reconfirms_when_sql_changed():
    stale = _cells_decision({"cube": "old", "dashboard": "d1"})
    applied = apply([stale], [], {"enrollment": FP}, cell_diffs=[DIFF])
    assert applied.reconfirm == [stale] and applied.open_cells == [DIFF]


def test_cells_decision_with_no_differences_is_no_longer_needed():
    applied = apply([_cells_decision()], [], {"enrollment": FP}, cell_diffs=[])
    assert applied.no_longer_needed == [_cells_decision()]


# --- cause decisions (T17) ---------------------------------------------------

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.decisions import (  # noqa: E402
    cause_covers,
    group_keys,
    mask_step,
    step_fingerprint,
)

LABEL_A = "main: s.section_id IS NOT NULL"
LABEL_B = "main: d.week_start <= a.score_date"


def _school(value, n_students=12, grade="7", comparison_id="enrollment"):
    return Group(
        comparison_id,
        (("region", value), ("grade_level", grade)),
        "dashboard_only",
        n_students * 2,
        n_students,
    )


def _cause(id="c1", label=LABEL_A, groups=(), side="cube", call="deliberate",
           fingerprints=None, comparison="enrollment"):  # fmt: skip
    return Decision(
        id=id,
        comparison=comparison,
        call=call,
        reason="known",
        cause={"side": side, "step": mask_step(label), "groups": list(groups)},
        fingerprints=(
            {**FP, "step": step_fingerprint(label)}
            if fingerprints is None
            else fingerprints
        ),
    )


def test_group_keys_show_a_reviewed_value_only_for_10_or_more_students():
    big, small = _school("Newark"), _school("Camden", n_students=4)

    assert group_keys([big, small]) == [
        "enrollment:region=Newark,grade_level=7",
        "enrollment:region=<redacted>,grade_level=<redacted>",
    ]


def test_group_keys_number_colliding_masked_keys_by_raw_dims():
    a, b = _school("Paterson", n_students=4), _school("Camden", n_students=4)

    assert group_keys([a, b]) == group_keys([b, a])[::-1]
    assert group_keys([a, b]) == [
        "enrollment:region=<redacted>,grade_level=<redacted>#2",
        "enrollment:region=<redacted>,grade_level=<redacted>",
    ]


def test_step_fingerprint_changes_when_the_label_changes():
    assert step_fingerprint(LABEL_A) == step_fingerprint(LABEL_A)
    assert step_fingerprint(LABEL_A) != step_fingerprint(LABEL_A + " AND x")
    # The masked text is the same; the hash of the full label tells them apart.
    one, two = "main: t.term = 20240701", "main: t.term = 20250701"
    assert mask_step(one) == mask_step(two) == "main: t.term = <n>"
    assert step_fingerprint(one) != step_fingerprint(two)


def test_mask_step_masks_runs_of_5_or_more_digits_only():
    assert mask_step("x IN (1234, 12345, 9876543210)") == "x IN (1234, <n>, <n>)"
    assert mask_step("grade_level >= 9") == "grade_level >= 9"


def test_cause_decision_quiets_the_groups_it_lists_in_its_comparison():
    newark, camden = _school("Newark"), _school("Camden")
    elsewhere = _school("Newark", comparison_id="other")
    key = "enrollment:region=Newark,grade_level=7"

    applied = apply([_cause(groups=[key])], [newark, camden, elsewhere], {
        "enrollment": FP, "other": FP})  # fmt: skip

    assert [(d.id, g) for d, g in applied.quiet_causes] == [("c1", newark)]
    assert applied.open == [camden, elsewhere]
    assert applied.quiet == []


def test_cause_decision_with_stale_sql_or_no_step_fingerprint_reconfirms():
    newark = _school("Newark")
    key = "enrollment:region=Newark,grade_level=7"
    stale = _cause(groups=[key], fingerprints={"cube": "old", "dashboard": "d1",
                                                "step": step_fingerprint(LABEL_A)})  # fmt: skip
    no_step = _cause(id="c2", label=LABEL_B, groups=[key], fingerprints=dict(FP))

    for decision in (stale, no_step):
        applied = apply([decision], [newark], {"enrollment": FP})
        assert applied.reconfirm == [decision] and applied.open == [newark]


def test_cause_decision_keys_matching_no_group_are_stale():
    newark = _school("Newark")
    key = "enrollment:region=Newark,grade_level=7"

    partly = apply([_cause(groups=[key, "enrollment:gone"])], [newark],
                   {"enrollment": FP})  # fmt: skip
    gone = apply([_cause(groups=["enrollment:gone"])], [newark], {"enrollment": FP})

    assert [(d.id, keys) for d, keys in partly.partly_stale] == [
        ("c1", ["enrollment:gone"])
    ]
    assert [d.id for d in gone.no_longer_needed] == ["c1"]


def test_a_group_split_across_2_causes_needs_both_to_stay_quiet():
    newark = _school("Newark")
    key = "enrollment:region=Newark,grade_level=7"
    a = _cause("a", LABEL_A, [key])
    b = _cause("b", LABEL_B, [key], side="dashboard")
    stale_b = _cause("b", LABEL_B, [key], side="dashboard",
                     fingerprints={**FP, "cube": "old"})  # fmt: skip

    both = apply([a, b], [newark], {"enrollment": FP})
    half = apply([a, stale_b], [newark], {"enrollment": FP})

    assert [d.id for d, _ in both.quiet_causes] == ["a", "b"]
    assert both.open == [] and both.groups() == [newark]
    assert half.open == [newark] and half.quiet_causes == []
    assert half.reconfirm == [stale_b]


def test_cause_covers_an_item_only_when_every_label_has_a_decision():
    key = "enrollment:region=Newark,grade_level=7"
    labels = [("cube", LABEL_A), ("dashboard", LABEL_B)]
    a = _cause("a", LABEL_A, [key])
    b = _cause("b", LABEL_B, [key], side="dashboard")
    b_wrong_side = _cause("b", LABEL_B, [key], side="cube")

    assert not cause_covers([a], "enrollment", key, labels)
    assert not cause_covers([a, b_wrong_side], "enrollment", key, labels)
    assert cause_covers([a, b], "enrollment", key, labels)
    assert not cause_covers([a, b], "other", key, labels)
    assert not cause_covers([a, b], "enrollment", "enrollment:x", labels)


def test_group_and_cause_decisions_coexist():
    newark, camden = _school("Newark"), _school("Camden")
    by_value = _decision(values=["Camden"])

    applied = apply(
        [by_value, _cause(groups=["enrollment:region=Newark,grade_level=7"])],
        [newark, camden],
        {"enrollment": FP},
    )

    assert [(d.id, g) for d, g in applied.quiet] == [("d1", camden)]
    assert [(d.id, g) for d, g in applied.quiet_causes] == [("c1", newark)]
    assert applied.open == []


def test_a_group_and_a_cause_decision_agreeing_on_one_group_leave_it_to_the_group():
    newark = _school("Newark")
    cause = _cause(groups=["enrollment:region=Newark,grade_level=7"])

    applied = apply([_decision(), cause], [newark], {"enrollment": FP})

    assert [(d.id, g) for d, g in applied.quiet] == [("d1", newark)]
    assert applied.quiet_causes == [] and applied.groups() == [newark]


def test_a_group_and_a_cause_decision_disagreeing_on_one_group_raise():
    cause = _cause(call="fix_cube", groups=["enrollment:region=Newark,grade_level=7"])

    with pytest.raises(ValueError, match=r"d1.*c1.*disagree|c1.*d1.*disagree"):
        apply([_decision(), cause], [_school("Newark")], {"enrollment": FP})


def test_two_cause_decisions_on_one_step_raise():
    key = "enrollment:region=Newark,grade_level=7"

    with pytest.raises(ValueError, match="c1.*c2.*both"):
        apply([_cause("c1", groups=[key]), _cause("c2", groups=[key])],
              [_school("Newark")], {"enrollment": FP})  # fmt: skip
