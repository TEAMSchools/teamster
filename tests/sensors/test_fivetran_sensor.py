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
