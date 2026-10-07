import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py puts docs/ on sys.path at runtime
from launch.build import Catalog, validate

GOOD_ENTRY = {
    "id": "attendance_dashboard",
    "name": "Attendance Dashboard",
    "url": "https://tableau.kipp.org/t/KIPPNJ/views/Attendance",
    "system": "tableau",
    "status": "needs-review",
    "group": "attendance",
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


VERIFIED = {
    **GOOD_ENTRY,
    "status": "verified",
    "description": "Monitor ADA and chronic absenteeism.",
    "audiences": ["leaders", "ops"],
}


def test_tier_two_passes_a_complete_verified_entry():
    assert validate(make_catalog(entries=[VERIFIED]), [VERIFIED]) == []


def test_tier_two_requires_a_description():
    entry = {**VERIFIED, "description": "  "}
    errors = validate(make_catalog(entries=[entry]), [entry])
    assert any("description" in e for e in errors)


def test_tier_two_requires_audiences():
    entry = {**VERIFIED, "audiences": []}
    errors = validate(make_catalog(entries=[entry]), [entry])
    assert any("audiences" in e for e in errors)


def test_tier_two_rejects_an_unknown_audience():
    entry = {**VERIFIED, "audiences": ["parents"]}
    errors = validate(make_catalog(entries=[entry]), [entry])
    assert any("parents" in e for e in errors)


def test_tier_two_requires_https_on_a_guide():
    entry = {**VERIFIED, "guide": "http://guide.test"}
    errors = validate(make_catalog(entries=[entry]), [entry])
    assert any("guide" in e for e in errors)


def test_tier_two_is_not_applied_to_unverified_entries():
    draft = {**GOOD_ENTRY, "description": "", "audiences": []}
    assert validate(make_catalog(entries=[draft]), []) == []


def test_family_member_needs_exactly_one_real_region():
    member = {
        **VERIFIED,
        "id": "gpa_roster_camden",
        "name": "GPA Roster: Camden",
        "regions": ["all"],
    }
    config = {
        **GOOD_CONFIG,
        "families": [
            {
                "id": "gpa_roster",
                "name": "GPA Roster",
                "description": "d",
                "group": "attendance",
                "members": ["GPA Roster: Camden"],
            }
        ],
    }
    errors = validate(make_catalog(entries=[member], config=config), [member])
    assert any("region" in e for e in errors)


def test_tier_one_requires_a_known_group():
    entry = {**GOOD_ENTRY, "group": "nonexistent"}
    errors = validate(make_catalog(entries=[entry]), [])
    assert any("group" in e for e in errors)


def test_tier_one_requires_group_to_be_present():
    entry = {k: v for k, v in GOOD_ENTRY.items()}
    entry.pop("group", None)
    errors = validate(make_catalog(entries=[entry]), [])
    assert any("group" in e for e in errors)


@pytest.mark.parametrize(
    "value",
    [None, "25", 3.5, [25]],
)
def test_minimum_verified_must_be_an_int(value):
    config = {**GOOD_CONFIG, "minimum_verified": value}
    errors = validate(make_catalog(config=config), [])
    assert any("minimum_verified" in e for e in errors), errors


def test_minimum_verified_rejects_bool():
    # isinstance(True, int) is True in Python -- a bare isinstance check
    # would silently accept `minimum_verified: true` as 1.
    config = {**GOOD_CONFIG, "minimum_verified": True}
    errors = validate(make_catalog(config=config), [])
    assert any("minimum_verified" in e for e in errors), errors


def test_minimum_verified_rejects_negative():
    config = {**GOOD_CONFIG, "minimum_verified": -1}
    errors = validate(make_catalog(config=config), [])
    assert any("minimum_verified" in e for e in errors), errors


def test_minimum_verified_missing_is_rejected():
    config = {k: v for k, v in GOOD_CONFIG.items() if k != "minimum_verified"}
    errors = validate(make_catalog(config=config), [])
    assert any("minimum_verified" in e for e in errors), errors


def test_minimum_verified_zero_is_allowed():
    config = {**GOOD_CONFIG, "minimum_verified": 0}
    assert validate(make_catalog(config=config), []) == []


def test_promo_url_must_be_https():
    config = {
        **GOOD_CONFIG,
        "promos": [{"label": "X", "blurb": "y", "url": "http://insecure.test"}],
    }
    errors = validate(make_catalog(config=config), [])
    assert any("https" in e for e in errors), errors


def test_promo_url_rejects_javascript_scheme():
    config = {
        **GOOD_CONFIG,
        "promos": [{"label": "X", "blurb": "y", "url": "javascript:alert(1)"}],
    }
    errors = validate(make_catalog(config=config), [])
    assert any("https" in e for e in errors), errors
