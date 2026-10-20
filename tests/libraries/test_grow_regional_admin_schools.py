from teamster.libraries.level_data.grow.assets import (
    normalize_regional_admin_schools,
)


def test_normalize_regional_admin_schools():
    records = [
        {"_id": "u1", "regionalAdminSchools": ["s1", "s2"]},
        {"_id": "u2", "regionalAdminSchools": [{"0": "s3", "1": "s4"}]},
        {"_id": "u3", "regionalAdminSchools": [{"_id": "s5", "name": "School 5"}]},
        {"_id": "u4", "regionalAdminSchools": []},
        {"_id": "u5", "regionalAdminSchools": None},
        {"_id": "u6"},
    ]

    normalize_regional_admin_schools(records)

    assert [r.get("regionalAdminSchools") for r in records] == [
        [{"_id": "s1", "name": None}, {"_id": "s2", "name": None}],
        [{"_id": "s3", "name": None}, {"_id": "s4", "name": None}],
        [{"_id": "s5", "name": "School 5"}],
        [],
        None,
        None,
    ]
