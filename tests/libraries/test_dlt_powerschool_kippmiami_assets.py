"""Miami's off-by-default PowerSchool dlt assets cover the frozen archive."""

import importlib.util

# One dlt table per stg_powerschool__* table in the kippmiami_powerschool archive.
ARCHIVE_TABLES = {
    "assignmentcategoryassoc",
    "assignmentscore",
    "assignmentsection",
    "attendance",
    "attendance_code",
    "attendance_conversion_items",
    "bell_schedule",
    "calendar_day",
    "cc",
    "codeset",
    "courses",
    "cycle_day",
    "districtteachercategory",
    "emailaddress",
    "fte",
    "gen",
    "gradecalcformulaweight",
    "gradecalcschoolassoc",
    "gradecalculationtype",
    "gradeformulaset",
    "gradescaleitem",
    "gradeschoolconfig",
    "gradeschoolformulaassoc",
    "gradesectionconfig",
    "log",
    "originalcontactmap",
    "person",
    "personaddress",
    "personaddressassoc",
    "personemailaddressassoc",
    "personphonenumberassoc",
    "pgfinalgrades",
    "phonenumber",
    "prefs",
    "reenrollments",
    "roledef",
    "schools",
    "schoolstaff",
    "sections",
    "sectionteacher",
    "spenrollments",
    "storedgrades",
    "studentcontactassoc",
    "studentcontactdetail",
    "studentcorefields",
    "students",
    "studenttest",
    "studenttestscore",
    "teachercategory",
    "termbins",
    "terms",
    "test",
    "testscore",
    "u_clg_et_stu",
    "u_clg_et_stu_alt",
    "u_studentsuserfields",
    "users",
    "userscorefields",
}


def test_miami_assets_cover_exactly_the_archive_tables():
    from teamster.code_locations.kippmiami.powerschool.sis.dlt.assets import assets

    keys = {k.to_user_string() for a in assets for k in a.keys}

    assert len(ARCHIVE_TABLES) == 58
    assert keys == {f"kippmiami/powerschool/sis/{t}" for t in ARCHIVE_TABLES}


def test_miami_assets_op_and_pool():
    from teamster.code_locations.kippmiami.powerschool.sis.dlt.assets import assets

    assert len(assets) == 1
    assert assets[0].op.name == "kippmiami__powerschool"
    assert assets[0].op.pool == "dlt_powerschool_kippmiami"


def test_miami_has_no_powerschool_triggers():
    prefix = "teamster.code_locations.kippmiami.powerschool.sis.dlt"

    assert importlib.util.find_spec(prefix) is not None
    assert importlib.util.find_spec(f"{prefix}.sensors") is None
    assert importlib.util.find_spec(f"{prefix}.schedules") is None
