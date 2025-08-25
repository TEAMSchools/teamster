from dagster import AssetsDefinition, materialize


def _test_asset(assets: list[AssetsDefinition], selection: str):
    from teamster.core.resources import SSH_COUCHDROP, get_io_manager_gcs_avro

    result = materialize(
        assets=assets,
        selection=selection,
        resources={
            "ssh_couchdrop": SSH_COUCHDROP,
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
        },
    )

    assert result.success

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_powerschool_attendance_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/attendance")


def test_powerschool_attendance_code_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/attendance_code"
    )


def test_powerschool_attendance_conversion_items_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets,
        selection="kipppaterson/powerschool/sis/sftp/attendance_conversion_items",
    )


def test_powerschool_bell_schedule_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/bell_schedule"
    )


def test_powerschool_calendar_day_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/calendar_day"
    )


def test_powerschool_cc_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/cc")


def test_powerschool_codeset_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/codeset")


def test_powerschool_courses_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/courses")


def test_powerschool_cycle_day_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/cycle_day")


def test_powerschool_emailaddress_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/emailaddress"
    )


def test_powerschool_fte_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/fte")


def test_powerschool_gen_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/gen")


def test_powerschool_originalcontactmap_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/originalcontactmap"
    )


def test_powerschool_person_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/person")


def test_powerschool_personaddress_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/personaddress"
    )


def test_powerschool_personaddressassoc_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/personaddressassoc"
    )


def test_powerschool_personemailaddressassoc_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets,
        selection="kipppaterson/powerschool/sis/sftp/personemailaddressassoc",
    )


def test_powerschool_personphonenumberassoc_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets,
        selection="kipppaterson/powerschool/sis/sftp/personphonenumberassoc",
    )


def test_powerschool_phonenumber_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/phonenumber"
    )


def test_powerschool_reenrollments_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/reenrollments"
    )


def test_powerschool_s_nj_crs_x_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/s_nj_crs_x")


def test_powerschool_s_nj_ren_x_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/s_nj_ren_x")


def test_powerschool_s_nj_stu_x_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/s_nj_stu_x")


def test_powerschool_schools_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/schools")


def test_powerschool_schoolstaff_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/schoolstaff"
    )


def test_powerschool_sections_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/sections")


def test_powerschool_spenrollments_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/spenrollments"
    )


def test_powerschool_studentcontactassoc_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/studentcontactassoc"
    )


def test_powerschool_studentcontactdetail_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets,
        selection="kipppaterson/powerschool/sis/sftp/studentcontactdetail",
    )


def test_powerschool_studentcorefields_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(
        assets=assets, selection="kipppaterson/powerschool/sis/sftp/studentcorefields"
    )


def test_powerschool_students_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/students")


def test_powerschool_termbins_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/termbins")


def test_powerschool_terms_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/terms")


def test_powerschool_users_kipppaterson():
    from teamster.code_locations.kipppaterson.powerschool.sis.sftp.assets import assets

    _test_asset(assets=assets, selection="kipppaterson/powerschool/sis/sftp/users")
