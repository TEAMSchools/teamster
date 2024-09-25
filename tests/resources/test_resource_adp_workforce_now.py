import json
import pathlib

from dagster import EnvVar, build_resources

from teamster.libraries.adp.workforce_now.api.resources import AdpWorkforceNowResource

with build_resources(
    resources={
        "adp_wfn": AdpWorkforceNowResource(
            client_id=EnvVar("ADP_WFN_CLIENT_ID"),
            client_secret=EnvVar("ADP_WFN_CLIENT_SECRET"),
            cert_filepath="/etc/secret-volume/adp_wfn_cert",
            key_filepath="/etc/secret-volume/adp_wfn_key",
            masked=False,
        ),
    }
) as resources:
    ADP_WFN: AdpWorkforceNowResource = resources.adp_wfn


def test_event_notification():
    r = ADP_WFN._request(
        method="GET",
        url=f"{ADP_WFN._service_root}/core/v1/event-notification-messages",
    )

    print(r.json())


def _test_get_worker(as_of_date: str, aoid: str | None = None):
    params = {
        "asOfDate": as_of_date,
        "$select": ",".join(
            [
                "workers/associateOID",
                "workers/workerID",
                "workers/workerDates",
                "workers/workerStatus",
                "workers/businessCommunication",
                "workers/workAssignments",
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
            ]
        ),
    }

    if aoid is not None:
        data = ADP_WFN.get(endpoint=f"hr/v2/workers/{aoid}", params=params).json()
        filepath = pathlib.Path(f"env/test/adp/{aoid}.json")
    else:
        data = ADP_WFN.get_records(endpoint="hr/v2/workers", params=params)
        filepath = pathlib.Path("env/test/adp/workers.json")

    filepath.parent.mkdir(parents=True, exist_ok=True)

    json.dump(obj=data, fp=filepath.open(mode="w"))


def test_get_worker():
    _test_get_worker(as_of_date="01/29/2024", aoid="G3R8E9HV8QXW9AWE")


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


def test_get_workers():
    _test_get_worker(as_of_date="")
