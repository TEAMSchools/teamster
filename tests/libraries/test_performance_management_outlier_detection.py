import math

import numpy
import pandas

from teamster.libraries.performance_management.outlier_detection import (
    ETR_COLUMNS,
    MEASURE_SET_COLUMNS,
    score_partition,
)

SO_COLUMNS = [f"so{i}" for i in range(1, 9)]
CORE_VALUE_COLUMNS = [
    "excellence",
    "fun",
    "kid_focus",
    "presence",
    "punctuality",
    "radical_love",
    "team",
]


def _rows(
    measure_set: str, academic_year: int, form_term: str, n: int, start_id: int
) -> list[dict]:
    rng = numpy.random.default_rng(start_id)

    scored = MEASURE_SET_COLUMNS[measure_set]

    rows = []
    for i in range(n):
        row = {
            "observer_employee_number": start_id + i,
            "academic_year": academic_year,
            "form_term": form_term,
            "term_num": int(form_term[-1]),
            "measure_set": measure_set,
        }

        for col in ETR_COLUMNS + SO_COLUMNS + CORE_VALUE_COLUMNS:
            row[col] = float(rng.uniform(1, 4)) if col in scored else math.nan

        row["overall_score"] = float(rng.uniform(1, 4))
        rows.append(row)

    return rows


def _frame(*groups: tuple[str, int, str, int]) -> pandas.DataFrame:
    rows = []
    start_id = 1000
    for measure_set, academic_year, form_term, n in groups:
        rows.extend(_rows(measure_set, academic_year, form_term, n, start_id))
        start_id += 1000

    return pandas.DataFrame(rows)


def _by_observer(records: list[dict]) -> dict[int, dict]:
    return {r["observer_employee_number"]: r for r in records}


def test_etr_values_rows_survive_null_so_columns():
    df = _frame(("etr_so", 2025, "PM3", 10), ("etr_values", 2026, "PM2", 8))

    records = score_partition(df, 2026, "PM2")

    assert len(records) == 8
    assert {r["measure_set"] for r in records} == {"etr_values"}
    assert all(r["pc1_current"] is not None for r in records)


def test_etr_so_rows_survive_null_core_value_columns():
    df = _frame(("etr_so", 2025, "PM3", 10), ("etr_values", 2026, "PM2", 8))

    records = score_partition(df, 2025, "PM3")

    assert len(records) == 10
    assert all(r["pc1_current"] is not None for r in records)


def test_row_missing_own_measure_dropped():
    df = _frame(("etr_values", 2026, "PM2", 8))
    df.loc[0, "presence"] = math.nan

    records = score_partition(df, 2026, "PM2")

    assert len(records) == 7
    assert df.loc[0, "observer_employee_number"] not in _by_observer(records)


def test_small_group_emits_none():
    df = _frame(("etr_so", 2025, "PM3", 10), ("etr_values", 2026, "PM2", 2))

    records = score_partition(df, 2026, "PM2")

    assert len(records) == 2
    for r in records:
        for col in [
            "cluster_current",
            "tree_outlier_current",
            "is_iqr_outlier_current",
            "pc1_current",
            "cluster_global",
            "pc1_global",
        ]:
            assert r[col] is None, col


def test_records_carry_none_not_nan():
    df = _frame(("etr_values", 2026, "PM2", 8))

    records = score_partition(df, 2026, "PM2")

    assert all(r["so1"] is None for r in records)


def test_etr_values_rows_do_not_change_etr_so_global():
    so_only = _frame(("etr_so", 2024, "PM1", 10), ("etr_so", 2025, "PM3", 10))
    with_values = pandas.concat(
        [so_only, _frame(("etr_values", 2026, "PM2", 8))], ignore_index=True
    )

    before = _by_observer(score_partition(so_only, 2025, "PM3"))
    after = _by_observer(score_partition(with_values, 2025, "PM3"))

    assert before.keys() == after.keys()
    for key, row in before.items():
        for col in ["pc1_global", "pc2_global", "cluster_global"]:
            assert after[key][col] == row[col], col
        assert after[key]["is_iqr_outlier_global"] == row["is_iqr_outlier_global"]


def test_mixed_partition_fits_each_set():
    df = _frame(("etr_so", 2026, "PM2", 5), ("etr_values", 2026, "PM2", 5))

    records = score_partition(df, 2026, "PM2")

    assert len(records) == 10
    assert {r["measure_set"] for r in records} == {"etr_so", "etr_values"}
    assert all(r["pc1_current"] is not None for r in records)


def test_empty_partition_returns_no_records():
    df = _frame(("etr_so", 2025, "PM3", 10))

    assert score_partition(df, 2030, "PM1") == []
