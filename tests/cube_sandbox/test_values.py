from __future__ import annotations

import datetime as dt
import random

import pytest

from teamster.cube_sandbox import generate


def test_emails_fold_to_ascii() -> None:
    # google_email is matched exactly by resolveAccess, and a non-ASCII local
    # part needs SMTPUTF8 and is not what any real directory holds.
    email = generate.to_ascii_email("Ororo", "Munroe")
    assert email.isascii()
    assert email == "ororo.munroe@ktaf-sandbox.invalid"


def test_every_reserved_given_name_yields_a_usable_local_part() -> None:
    # A name with no ASCII at all folds to an EMPTY local part — an address
    # like ".taurasi@..." that is not a valid mailbox and resolves to nobody,
    # which is the precise failure ASCII-folding exists to prevent. The
    # non-Latin and right-to-left names that used to reach this guard are gone
    # (production has none), so nothing in the list exercises it today. The
    # guard stays because the next name added might.
    for entry in generate.reserved_given_names():
        email = generate.to_ascii_email(entry["name"], "Taurasi")
        local = email.split("@")[0]
        given_part, _, surname_part = local.partition(".")
        assert email.isascii(), entry
        assert given_part, f"{entry['name']} folded to an empty local part"
        assert surname_part == "taurasi"


def test_latin_extended_letters_transliterate_rather_than_vanish() -> None:
    # NFKD does not decompose ø, æ or ß — they carry no combining mark — so a
    # drop-what-is-not-ASCII fold turns Søren into "sren".
    assert generate.to_ascii_email("Søren", "Odinson").startswith("soren.")


def test_distinct_given_names_do_not_collide_on_one_surname() -> None:
    # resolveAccess reads ONE dim_staff_cube_access row per google_email. Two
    # synthetic people sharing an address makes whichever row wins arbitrary,
    # and the persona then tests something other than what it declares.
    locals_ = {
        generate.to_ascii_email(e["name"], "Taurasi")
        for e in generate.reserved_given_names()
    }
    assert len(locals_) == len(generate.reserved_given_names())


def test_birth_date_follows_grade() -> None:
    # A 3rd grader born in 1998 breaks every age calculation downstream.
    born = generate.birth_date_for_grade(3, 2026, random.Random(0))
    age = 2026 - born.year
    assert 7 <= age <= 11, f"implausible age {age} for grade 3"


def test_birth_dates_stay_plausible_across_every_grade_and_seed() -> None:
    for grade in range(13):
        for seed in range(50):
            born = generate.birth_date_for_grade(grade, 2026, random.Random(seed))
            age = 2026 - born.year
            assert grade + 4 <= age <= grade + 6, (grade, seed, born)
            assert isinstance(born, dt.date)


def test_an_off_cohort_minority_exists() -> None:
    # Retained, accelerated and late-entry students are real, and they are
    # what a kit gets wrong. A generator that emits only the typical age
    # teaches that age and grade are interchangeable.
    ages = {
        2026 - generate.birth_date_for_grade(5, 2026, random.Random(seed)).year
        for seed in range(200)
    }
    assert len(ages) > 1, "every student landed on the same age"


def test_birth_days_cover_month_ends() -> None:
    # Clamping the day to 1..28 makes a month-end or leap-day birthday
    # impossible. Those are domain reality, and they are what breaks naive age
    # arithmetic — the spec says reproduce domain reality, not smooth it away.
    days = {
        generate.birth_date_for_grade(4, 2026, random.Random(seed)).day
        for seed in range(400)
    }
    assert max(days) > 28


def test_surnames_come_from_the_reserved_set() -> None:
    rng = random.Random(0)
    _, surname = generate.fabricate_name(rng)
    assert surname in generate.reserved_surnames()


def test_given_names_come_from_the_reserved_set() -> None:
    rng = random.Random(0)
    given, _ = generate.fabricate_name(rng)
    assert given in {e["name"] for e in generate.reserved_given_names()}


def test_every_character_class_is_reachable() -> None:
    # The file's contract is that each given name carries the class it
    # exercises so coverage can assert every class is present. A class no
    # generator run can reach is a class nothing tests.
    rng = random.Random(0)
    drawn = {generate.fabricate_name(rng)[0] for _ in range(3000)}
    by_class: dict[str, set[str]] = {}
    for entry in generate.reserved_given_names():
        by_class.setdefault(entry["class"], set()).add(entry["name"])
    assert generate.given_name_classes() == set(by_class)
    for name_class, names in by_class.items():
        assert drawn & names, f"no {name_class} given name was ever drawn"


def test_fabricate_name_is_deterministic_for_a_seed() -> None:
    assert generate.fabricate_name(random.Random(3)) == generate.fabricate_name(
        random.Random(3)
    )


def test_the_sandbox_domain_is_invalid_per_rfc_2606() -> None:
    # .invalid never resolves, so a fabricated address cannot collide with a
    # real account and no mail can reach a synthetic person by accident.
    assert generate.SANDBOX_DOMAIN.endswith(".invalid")


@pytest.mark.parametrize("part", ["", "   ", "'-'"])
def test_a_name_with_no_usable_characters_still_yields_a_local_part(part: str) -> None:
    email = generate.to_ascii_email(part, "Odinson")
    assert email.split("@")[0].partition(".")[0]
    assert email.isascii()
