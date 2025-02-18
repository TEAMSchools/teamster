import json

from dagster import SensorResult, build_sensor_context

from teamster.code_locations.kipptaf.fivetran.sensors import (
    fivetran_connector_sync_status_sensor,
)
from teamster.code_locations.kipptaf.resources import FIVETRAN_RESOURCE
from teamster.core.resources import BIGQUERY_RESOURCE


def test_fivetran_connector_sync_status_sensor_initial():
    sensor_result = fivetran_connector_sync_status_sensor(
        context=build_sensor_context(),
        fivetran=FIVETRAN_RESOURCE,
        db_bigquery=BIGQUERY_RESOURCE,
    )

    assert isinstance(sensor_result, SensorResult)

    assert len(sensor_result.asset_events) > 0
    print(sensor_result.asset_events)

    assert sensor_result.cursor is not None
    print(sensor_result.cursor)


def test_fivetran_connector_sync_status_sensor_cursor():
    cursor = {
        "connectors": {
            "bellows_curliness": 1739516564.499,
            "genuine_describing": 1739559770.946,
            "jinx_credulous": 1739560595.53,
        },
        "assets": {
            "kipptaf__coupa__address": 1710781408.472,
            "kipptaf__coupa__business_group": 1715112208.086,
            "kipptaf__coupa__role": 1739516556.522,
            "kipptaf__coupa__user": 1739516557.63,
            "kipptaf__coupa__user_business_group_mapping": 1739516556.312,
            "kipptaf__coupa__user_role_mapping": 1739516557.425,
            "kipptaf__illuminate_xmin__dna_assessments__agg_student_responses": 1739559761.385,
            "kipptaf__illuminate_xmin__dna_assessments__agg_student_responses_group": 1739559757.63,
            "kipptaf__illuminate_xmin__dna_assessments__agg_student_responses_standard": 1739559763.956,
            "kipptaf__illuminate_xmin__dna_assessments__agg_students_assessments_scores": 1683859284.401,
            "kipptaf__illuminate_xmin__dna_assessments__students_assessments_archive": 1739545421.659,
            "kipptaf__illuminate__codes__dna_scopes": 1737390753.324,
            "kipptaf__illuminate__codes__dna_subject_areas": 1737390760.913,
            "kipptaf__illuminate__groups__group_student_aff": 1734106602.286,
            "kipptaf__illuminate__groups__groups": 1732292237.434,
            "kipptaf__illuminate__public__grade_levels": 1685716901.477,
            "kipptaf__illuminate__public__sessions": 1737391179.071,
            "kipptaf__illuminate__public__student_session_aff": 1739531849.51,
            "kipptaf__illuminate__public__students": 1739445383.874,
            "kipptaf__illuminate__public__users": 1739531842.995,
            "kipptaf__illuminate__standards__standards": 1739035061.493,
            "kipptaf__illuminate__standards__subjects": 1727536488.674,
            "kipptaf__illuminate__dna_assessments__assessment_grade_levels": 1739560587.078,
            "kipptaf__illuminate__dna_assessments__assessment_standards": 1739546260.571,
            "kipptaf__illuminate__dna_assessments__assessments": 1739560590.345,
            "kipptaf__illuminate__dna_assessments__assessments_reporting_groups": 1739290614.163,
            "kipptaf__illuminate__dna_assessments__field_standards": 1734351435.724,
            "kipptaf__illuminate__dna_assessments__fields": 1734362222.736,
            "kipptaf__illuminate__dna_assessments__fields_reporting_groups": 1734095798.348,
            "kipptaf__illuminate__dna_assessments__performance_band_sets": 1739459938.638,
            "kipptaf__illuminate__dna_assessments__performance_bands": 1739459938.503,
            "kipptaf__illuminate__dna_assessments__reporting_groups": 1737933631.975,
            "kipptaf__illuminate__dna_assessments__students_assessments": 1739560589.447,
            "kipptaf__illuminate__dna_assessments__tags": 1734365815.323,
            "kipptaf__illuminate__national_assessments__aptest_2019": 1727183760.677,
            "kipptaf__illuminate__national_assessments__aptest_2020": 1727183757.039,
            "kipptaf__illuminate__national_assessments__aptest_2021": 1727183753.711,
            "kipptaf__illuminate__national_assessments__aptest_2022": 1727277347.544,
            "kipptaf__illuminate__national_assessments__aptest_2023": 1727183763.244,
            "kipptaf__illuminate__national_assessments__aptest_2024": 1727277348.299,
            "kipptaf__illuminate__national_assessments__psat_2023": 1737390788.882,
            "kipptaf__illuminate__national_assessments__psat_2024": 1737390801.415,
            "kipptaf__illuminate__dna_repositories__fields": 1737390724.697,
            "kipptaf__illuminate__dna_repositories__repositories": 1739035029.965,
            "kipptaf__illuminate__dna_repositories__repository_grade_levels": 1737391171.963,
            "kipptaf__illuminate__dna_repositories__repository_365": 1737391256.542,
            "kipptaf__illuminate__dna_repositories__repository_413": 1737390896.664,
            "kipptaf__illuminate__dna_repositories__repository_425": 1737390965.209,
            "kipptaf__illuminate__dna_repositories__repository_426": 1737390960.137,
            "kipptaf__illuminate__dna_repositories__repository_427": 1737390938.055,
            "kipptaf__illuminate__dna_repositories__repository_428": 1737390986.669,
            "kipptaf__illuminate__dna_repositories__repository_429": 1737391067.454,
            "kipptaf__illuminate__dna_repositories__repository_430": 1737391278.28,
            "kipptaf__illuminate__dna_repositories__repository_431": 1737390967.305,
            "kipptaf__illuminate__dna_repositories__repository_432": 1737390934.277,
            "kipptaf__illuminate__dna_repositories__repository_433": 1737391066.495,
            "kipptaf__illuminate__dna_repositories__repository_434": 1737391211.058,
            "kipptaf__illuminate__dna_repositories__repository_435": 1737391058.007,
            "kipptaf__illuminate__dna_repositories__repository_436": 1737390996.738,
            "kipptaf__illuminate__dna_repositories__repository_437": 1737390916.803,
            "kipptaf__illuminate__dna_repositories__repository_438": 1737390928.807,
            "kipptaf__illuminate__dna_repositories__repository_439": 1737390926.022,
            "kipptaf__illuminate__dna_repositories__repository_440": 1737390994.627,
            "kipptaf__illuminate__dna_repositories__repository_441": 1737390995.193,
            "kipptaf__illuminate__dna_repositories__repository_442": 1737390952.37,
            "kipptaf__illuminate__dna_repositories__repository_443": 1737390911.889,
            "kipptaf__illuminate__dna_repositories__repository_444": 1737390984.702,
            "kipptaf__illuminate__dna_repositories__repository_445": 1737390950.884,
            "kipptaf__illuminate__dna_repositories__repository_446": 1738685852.715,
            "kipptaf__illuminate__dna_repositories__repository_447": 1739542582.962,
            "kipptaf__illuminate__dna_repositories__repository_448": 1737390846.322,
            "kipptaf__illuminate__dna_repositories__repository_449": 1737390845.062,
            "kipptaf__illuminate__dna_repositories__repository_450": 1738732694.418,
            "kipptaf__illuminate__dna_repositories__repository_451": 1739556992.649,
            "kipptaf__illuminate__dna_repositories__repository_452": 1737390850.509,
            "kipptaf__illuminate__dna_repositories__repository_453": 1737390849.241,
            "kipptaf__illuminate__dna_repositories__repository_454": 1738703830.344,
            "kipptaf__illuminate__dna_repositories__repository_455": 1739506672.842,
            "kipptaf__illuminate__dna_repositories__repository_456": 1737390853.224,
            "kipptaf__illuminate__dna_repositories__repository_457": 1737390852.592,
        },
    }

    sensor_result = fivetran_connector_sync_status_sensor(
        context=build_sensor_context(cursor=json.dumps(obj=cursor)),
        fivetran=FIVETRAN_RESOURCE,
        db_bigquery=BIGQUERY_RESOURCE,
    )

    if isinstance(sensor_result, SensorResult):
        assert len(sensor_result.asset_events) > 0
        print(sensor_result.asset_events)

        assert sensor_result.cursor is not None
        print(sensor_result.cursor)
