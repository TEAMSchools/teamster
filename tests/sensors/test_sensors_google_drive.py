import json

from dagster import SensorResult, build_sensor_context

from teamster.core.resources import GOOGLE_DRIVE_RESOURCE


def _test_sensor(sftp_sensor, cursor: dict | None = None):
    if cursor is None:
        cursor = {}

    context = build_sensor_context(
        sensor_name=sftp_sensor.name, cursor=json.dumps(obj=cursor)
    )

    result: SensorResult = sftp_sensor(
        context=context, google_drive=GOOGLE_DRIVE_RESOURCE
    )

    assert result.run_requests is not None
    assert len(result.run_requests) > 0

    for run_request in result.run_requests:
        context.log.info(run_request)

    print(result.cursor)


def test_couchdrop_sftp_sensor_kippcamden():
    from teamster.code_locations.kippcamden.couchdrop.sensors import (
        couchdrop_sftp_sensor,
    )

    _test_sensor(
        sftp_sensor=couchdrop_sftp_sensor,
        cursor={
            "kippcamden__pearson__njgpa": 1733760579,
            "kippcamden__pearson__njsla": 1725032365,
            "kippcamden__pearson__njsla_science": 1725033354,
            "kippcamden__pearson__student_list_report": 1746540340,
        },
    )


def test_couchdrop_sftp_sensor_kippmiami():
    from teamster.code_locations.kippmiami.couchdrop.sensors import (
        couchdrop_sftp_sensor,
    )

    _test_sensor(
        sftp_sensor=couchdrop_sftp_sensor,
        cursor={
            "kippmiami__fldoe__eoc": 1716380580,
            "kippmiami__fldoe__fast": 1748351082,
            "kippmiami__fldoe__fte": 1746634210,
            "kippmiami__fldoe__science": 1747849142,
        },
    )


def test_couchdrop_sftp_sensor_kippnewark():
    from teamster.code_locations.kippnewark.couchdrop.sensors import (
        couchdrop_sftp_sensor,
    )

    _test_sensor(
        sftp_sensor=couchdrop_sftp_sensor,
        cursor={
            "kippnewark__pearson__njgpa": 1730782802,
            "kippnewark__pearson__njsla": 1725032353,
            "kippnewark__pearson__njsla_science": 1725033292,
            "kippnewark__pearson__student_list_report": 1746539795,
        },
    )


def test_couchdrop_sftp_sensor_kipptaf():
    from teamster.code_locations.kipptaf.couchdrop.sensors import couchdrop_sftp_sensor

    _test_sensor(
        sftp_sensor=couchdrop_sftp_sensor,
        cursor={
            "kipptaf__tableau__view_count_per_view": 1743022988,
            "kipptaf__collegeboard__psat": 1735837254,
            "kipptaf__collegeboard__ap": 1746472259,
        },
    )
