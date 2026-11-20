from __future__ import annotations

from types import SimpleNamespace

from teamster.cube_sandbox import collisions


def _row(name: str, staff: int, students: int) -> SimpleNamespace:
    return SimpleNamespace(name=name, staff_hits=staff, student_hits=students)


def test_a_clean_sweep_reports_nothing() -> None:
    assert collisions.collisions([_row("Taurasi", 0, 0), _row("Jokić", 0, 0)]) == []


def test_one_student_is_enough_to_fail() -> None:
    # "Rare" and "absent" are different claims, and the reserved list makes
    # the second one. A single match means a surname from the list no longer
    # proves the row is fabricated.
    found = collisions.collisions([_row("Taurasi", 0, 0), _row("Grice", 0, 1)])

    assert found == [("Grice", 0, 1)]


def test_a_staff_only_match_fails_too() -> None:
    assert collisions.collisions([_row("Whalen", 1, 0)]) == [("Whalen", 1, 0)]


def test_the_clean_message_names_how_many_were_checked() -> None:
    # A checker that silently checked nothing reads exactly like a pass.
    message = collisions.describe([], 59)

    assert "59 reserved surnames checked" in message


def test_the_failure_message_carries_the_counts_and_the_remedy() -> None:
    message = collisions.describe([("Smith", 29, 378), ("Grice", 0, 2)], 60)

    assert "2 of 60" in message
    assert "Smith: 29 staff, 378 students" in message
    assert "Grice: 0 staff, 2 students" in message
    assert "Remove them" in message


def test_the_query_binds_names_rather_than_interpolating_them() -> None:
    # Surnames are caller data from a YAML file. BigQuery has no
    # REGEXP_ESCAPE, so a name carrying a metacharacter would change what a
    # pattern means; the query uses a bound parameter and space-padded token
    # matching instead of either interpolation or a regex.
    assert "@names" in collisions.COLLISION_SQL
    assert "REGEXP" not in collisions.COLLISION_SQL
    assert "STRPOS" in collisions.COLLISION_SQL


def test_the_query_reads_production_not_the_sandbox() -> None:
    # The whole point is comparing against real people. Pointed at the
    # sandbox it would compare the fabricated names to themselves and pass
    # while proving nothing.
    assert "teamster-332318" in collisions.COLLISION_SQL
    assert "teamster-cube-sandbox" not in collisions.COLLISION_SQL
