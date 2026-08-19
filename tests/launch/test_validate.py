import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py puts docs/ on sys.path at runtime
from launch.build import Catalog, validate

GOOD_ENTRY = {
    "id": "attendance_dashboard",
    "name": "Attendance Dashboard",
    "url": "https://tableau.kipp.org/t/KIPPNJ/views/Attendance",
    "system": "tableau",
    "status": "needs-review",
}

GOOD_CONFIG = {
    "minimum_verified": 25,
    "groups": [{"id": "attendance", "name": "Attendance & behavior"}],
    "families": [],
    "promos": [{"label": "Guides", "blurb": "All of them", "url": "https://x.test"}],
}


def make_catalog(entries=None, config=None) -> Catalog:
    return Catalog(
        entries=[dict(GOOD_ENTRY)] if entries is None else entries,
        config=GOOD_CONFIG if config is None else config,
        template="__CATALOG__",
    )


def test_a_clean_catalog_has_no_errors():
    assert validate(make_catalog(), []) == []


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        ({"id": None}, "id"),
        ({"id": "Not Valid"}, "id"),
        ({"name": ""}, "name"),
        ({"url": "http://insecure.test"}, "https"),
        ({"url": None}, "url"),
        ({"system": "notion"}, "system"),
        ({"status": "reviewed"}, "status"),
        ({"access": "open"}, "access"),
        ({"regions": ["brooklyn"]}, "region"),
    ],
)
def test_tier_one_rejects_bad_fields(mutate, fragment):
    entry = {**GOOD_ENTRY, **mutate}
    errors = validate(make_catalog(entries=[entry]), [])
    assert any(fragment in e for e in errors), errors


def test_duplicate_ids_are_rejected():
    errors = validate(make_catalog(entries=[dict(GOOD_ENTRY), dict(GOOD_ENTRY)]), [])
    assert any("duplicate" in e for e in errors)


def test_entries_must_be_a_list_of_mappings():
    errors = validate(make_catalog(entries=["just a string"]), [])
    assert any("mapping" in e for e in errors)


def test_entries_not_a_list_is_rejected():
    errors = validate(make_catalog(entries={"id": "a", "name": "A"}), [])
    assert errors == ["links.yml must be a list of entries"]


@pytest.mark.parametrize("missing_key", ["groups", "families", "promos"])
def test_missing_config_key_is_rejected(missing_key):
    config = {k: [] for k in ("groups", "families", "promos") if k != missing_key}
    errors = validate(make_catalog(config=config), [])
    assert any(missing_key in e for e in errors)


def test_family_naming_a_missing_entry_is_rejected():
    config = {
        **GOOD_CONFIG,
        "families": [
            {
                "id": "f",
                "name": "F",
                "description": "d",
                "group": "attendance",
                "members": ["Nonexistent Tool"],
            }
        ],
    }
    errors = validate(make_catalog(config=config), [])
    assert any("Nonexistent Tool" in e for e in errors)


def test_family_with_an_unknown_group_is_rejected():
    config = {
        **GOOD_CONFIG,
        "families": [
            {
                "id": "f",
                "name": "F",
                "description": "d",
                "group": "nope",
                "members": ["Attendance Dashboard"],
            }
        ],
    }
    errors = validate(make_catalog(config=config), [])
    assert any("nope" in e for e in errors)


def test_promo_pointing_nowhere_is_rejected():
    config = {**GOOD_CONFIG, "promos": [{"label": "X", "blurb": "y", "url": "#"}]}
    errors = validate(make_catalog(config=config), [])
    assert any("promo" in e for e in errors)


def test_every_problem_is_reported_not_just_the_first():
    entry = {**GOOD_ENTRY, "id": "BAD", "system": "notion", "url": "http://x.test"}
    errors = validate(make_catalog(entries=[entry]), [])
    assert len(errors) >= 3
