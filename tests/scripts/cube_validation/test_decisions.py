import pytest
from cube_validation.compare import Group
from cube_validation.config import Decision
from cube_validation.decisions import apply, sql_fingerprint

FP = {"cube": "c1", "dashboard": "d1"}


def _group(value="Newark", comparison_id="enrollment", column="region"):
    return Group(comparison_id, column, value, "value_differs", 3, 3)


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
