import json
import pathlib

from dagster import build_resources

from teamster.code_locations.kipptaf.resources import ADP_WORKFORCE_NOW_RESOURCE
from teamster.libraries.adp.workforce_now.api.resources import AdpWorkforceNowResource


def get_adp_wfn_resource() -> AdpWorkforceNowResource:
    with build_resources(
        resources={"adp_wfn": ADP_WORKFORCE_NOW_RESOURCE}
    ) as resources:
        return resources.adp_wfn


def test_event_notification():
    adp_wfn = get_adp_wfn_resource()

    r = adp_wfn._request(
        method="GET", url=f"{adp_wfn._service_root}/core/v1/event-notification-messages"
    )

    print(r.json())


def _test_get_worker(aoid: str | None = None, as_of_date: str | None = None):
    adp_wfn = get_adp_wfn_resource()

    params = {
        "asOfDate": as_of_date,
        "$select": ",".join(
            [
                "workers/associateOID",
                "workers/businessCommunication",
                "workers/customFieldGroup",
                "workers/languageCode",
                "workers/person/birthDate",
                "workers/person/communication",
                "workers/person/customFieldGroup",
                "workers/person/disabledIndicator",
                "workers/person/ethnicityCode",
                "workers/person/genderCode",
                "workers/person/genderSelfIdentityCode",
                "workers/person/highestEducationLevelCode",
                "workers/person/legalAddress",
                "workers/person/legalName",
                "workers/person/militaryClassificationCodes",
                "workers/person/militaryStatusCode",
                "workers/person/preferredName",
                "workers/person/raceCode",
                "workers/workAssignments",
                "workers/workerDates",
                "workers/workerID",
                "workers/workerStatus",
            ]
        ),
    }

    if aoid is not None:
        data = adp_wfn.get(endpoint=f"hr/v2/workers/{aoid}", params=params).json()
        filepath = pathlib.Path(f"env/test/adp/workers/{aoid}.json")
    else:
        data = adp_wfn.get_records(endpoint="hr/v2/workers", params=params)
        filepath = pathlib.Path("env/test/adp/workers/workers.json")

    filepath.parent.mkdir(parents=True, exist_ok=True)

    json.dump(obj=data, fp=filepath.open(mode="w"))


def test_get_worker():
    _test_get_worker(aoid="G3J18W59P8K8W9R9", as_of_date="07/02/2025")


def test_get_worker_list():
    test_cases = [
        {"aoid": "G3ASWDTVJ0WV2TAE", "as_of_date": "07/25/2024"},
        {"aoid": "G3ASWDTVJ0WV1BGB", "as_of_date": "08/14/2024"},
        {"aoid": "G3Z22CB7N12F1ZT0", "as_of_date": "08/13/2024"},
        {"aoid": "G3R8E9HV8QXW9AWE", "as_of_date": "01/29/2024"},
    ]

    for kwargs in test_cases:
        print(kwargs)
        _test_get_worker(**kwargs)


def test_get_workers_meta():
    adp_wfn = get_adp_wfn_resource()

    data = adp_wfn.get(endpoint="hr/v2/workers/meta").json()
    filepath = pathlib.Path("env/test/adp/workers/meta.json")

    filepath.parent.mkdir(parents=True, exist_ok=True)

    json.dump(obj=data, fp=filepath.open(mode="w"))
