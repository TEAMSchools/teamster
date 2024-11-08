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
            "sameness_cunning": 1723450048.417,
            "bellows_curliness": 1723449958.987,
            "regency_carrying": 1723457999.419,
            "genuine_describing": 1723474975.763,
            "jinx_credulous": 1723475700.144,
            "muskiness_cumulative": 1723457833.448,
        },
        "assets": {
            "kipptaf__adp_workforce_now__business_communication": 1723449993.769,
            "kipptaf__adp_workforce_now__classification": 1723450038.107,
            "kipptaf__adp_workforce_now__groups": 1723450003.41,
            "kipptaf__adp_workforce_now__location": 1723450027.89,
            "kipptaf__adp_workforce_now__organizational_unit": 1723449979.503,
            "kipptaf__adp_workforce_now__other_personal_address": 1723450005.308,
            "kipptaf__adp_workforce_now__person_communication": 1723450002.983,
            "kipptaf__adp_workforce_now__person_disability": 1723450036.134,
            "kipptaf__adp_workforce_now__person_history": 1723449986.933,
            "kipptaf__adp_workforce_now__person_military_classification": 1723450042.275,
            "kipptaf__adp_workforce_now__person_preferred_salutation": 1723450014.356,
            "kipptaf__adp_workforce_now__person_social_insurance_program": 1723450041.337,
            "kipptaf__adp_workforce_now__work_assignment_history": 1723449987.644,
            "kipptaf__adp_workforce_now__worker": 1723449992.876,
            "kipptaf__adp_workforce_now__worker_additional_remuneration": 1723450010.341,
            "kipptaf__adp_workforce_now__worker_assigned_location": 1723450034.744,
            "kipptaf__adp_workforce_now__worker_assigned_organizational_unit": 1723450007.827,
            "kipptaf__adp_workforce_now__worker_base_remuneration": 1723449981.513,
            "kipptaf__adp_workforce_now__worker_classification": 1723450016.738,
            "kipptaf__adp_workforce_now__worker_group": 1723450029.632,
            "kipptaf__adp_workforce_now__worker_home_organizational_unit": 1723450035.841,
            "kipptaf__adp_workforce_now__worker_report_to": 1723450042.507,
            "kipptaf__coupa__address": 1710781408.472,
            "kipptaf__coupa__business_group": 1715112208.086,
            "kipptaf__coupa__role": 1723449855.899,
            "kipptaf__coupa__user": 1723449856.883,
            "kipptaf__coupa__user_business_group_mapping": 1723449880.422,
            "kipptaf__coupa__user_role_mapping": 1723449869.48,
            "kipptaf__facebook_pages__daily_page_metrics_total": 1723457976.672,
            "kipptaf__facebook_pages__lifetime_post_metrics_total": 1723457972.712,
            "kipptaf__facebook_pages__post_history": 1723457975.393,
            "kipptaf__illuminate_xmin__dna_assessments__agg_student_responses": 1722978109.663,
            "kipptaf__illuminate_xmin__dna_assessments__agg_student_responses_group": 1722949326.966,
            "kipptaf__illuminate_xmin__dna_assessments__agg_student_responses_standard": 1722978106.489,
            "kipptaf__illuminate_xmin__dna_assessments__agg_students_assessments_scores": 1683859284.401,
            "kipptaf__illuminate_xmin__dna_assessments__students_assessments_archive": 1723010502.472,
            "kipptaf__illuminate__codes__dna_scopes": 1706044599.664,
            "kipptaf__illuminate__codes__dna_subject_areas": 1699571784.053,
            "kipptaf__illuminate__groups__group_student_aff": 1715105629.807,
            "kipptaf__illuminate__groups__groups": 1722003317.108,
            "kipptaf__illuminate__public__grade_levels": 1685716901.477,
            "kipptaf__illuminate__public__sessions": 1721794518.486,
            "kipptaf__illuminate__public__student_session_aff": 1723457739.538,
            "kipptaf__illuminate__public__students": 1723371330.325,
            "kipptaf__illuminate__public__users": 1723457735.591,
            "kipptaf__illuminate__standards__standards": 1723302909.892,
            "kipptaf__illuminate__standards__subjects": 1722042872.732,
            "kipptaf__illuminate__dna_assessments__assessment_grade_levels": 1723418086.268,
            "kipptaf__illuminate__dna_assessments__assessment_standards": 1723414518.729,
            "kipptaf__illuminate__dna_assessments__assessments": 1723475693.637,
            "kipptaf__illuminate__dna_assessments__assessments_reporting_groups": 1723234486.645,
            "kipptaf__illuminate__dna_assessments__field_standards": 1723414517.384,
            "kipptaf__illuminate__dna_assessments__fields": 1723475686.229,
            "kipptaf__illuminate__dna_assessments__fields_reporting_groups": 1723234488.065,
            "kipptaf__illuminate__dna_assessments__performance_band_sets": 1723234486.9,
            "kipptaf__illuminate__dna_assessments__performance_bands": 1723234486.395,
            "kipptaf__illuminate__dna_assessments__reporting_groups": 1722024961.618,
            "kipptaf__illuminate__dna_assessments__students_assessments": 1718331275.46,
            "kipptaf__illuminate__dna_assessments__tags": 1723414516.632,
            "kipptaf__illuminate__national_assessments__psat_2023": 1716560086.932,
            "kipptaf__illuminate__national_assessments__psat_2024": 1719418464.432,
            "kipptaf__illuminate__dna_repositories__fields": 1710184462.144,
            "kipptaf__illuminate__dna_repositories__repositories": 1710184461.586,
            "kipptaf__illuminate__dna_repositories__repository_grade_levels": 1710180769.758,
            "kipptaf__illuminate__dna_repositories__repository_365": 1699996633.778,
            "kipptaf__illuminate__dna_repositories__repository_413": 1697717729.318,
            "kipptaf__illuminate__dna_repositories__repository_425": 1688261198.159,
            "kipptaf__illuminate__dna_repositories__repository_426": 1699881401.985,
            "kipptaf__illuminate__dna_repositories__repository_427": 1700140453.666,
            "kipptaf__illuminate__dna_repositories__repository_428": 1698693327.219,
            "kipptaf__illuminate__dna_repositories__repository_429": 1706307141.506,
            "kipptaf__illuminate__dna_repositories__repository_430": 1706195834.053,
            "kipptaf__illuminate__dna_repositories__repository_431": 1706224400.993,
            "kipptaf__illuminate__dna_repositories__repository_432": 1712859199.869,
            "kipptaf__illuminate__dna_repositories__repository_433": 1706631111.554,
            "kipptaf__illuminate__dna_repositories__repository_434": 1706573536.571,
            "kipptaf__illuminate__dna_repositories__repository_435": 1712549550.485,
            "kipptaf__illuminate__dna_repositories__repository_436": 1713283981.392,
            "kipptaf__illuminate__dna_repositories__repository_437": 1713388318.202,
            "kipptaf__illuminate__dna_repositories__repository_438": 1713276769.024,
            "kipptaf__illuminate__dna_repositories__repository_439": 1713103954.782,
            "kipptaf__illuminate__dna_repositories__repository_440": 1713204783.168,
            "kipptaf__illuminate__dna_repositories__repository_441": 1718118897.216,
            "kipptaf__illuminate__dna_repositories__repository_442": 1717776872.146,
            "kipptaf__illuminate__dna_repositories__repository_443": 1717942530.139,
            "kipptaf__instagram_business__media_history": 1723457824.372,
            "kipptaf__instagram_business__media_insights": 1723457827.138,
            "kipptaf__instagram_business__user_history": 1723457822.568,
            "kipptaf__instagram_business__user_insights": 1723457822.496,
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
