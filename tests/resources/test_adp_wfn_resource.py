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


def test_get_worker():
    aoid = "G3R8E9HV8QXWE5TE"
    params = {
        "asOfDate": "01/01/2021",
        # "$select": ",".join(
        #     [
        #         "workers/associateOID",
        #         "workers/workerID",
        #         "workers/workerDates",
        #         "workers/workerStatus",
        #         "workers/businessCommunication",
        #         "workers/workAssignments",
        #         "workers/customFieldGroup",
        #         "workers/languageCode",
        #         "workers/person/birthDate",
        #         "workers/person/communication",
        #         "workers/person/customFieldGroup",
        #         "workers/person/disabledIndicator",
        #         "workers/person/ethnicityCode",
        #         "workers/person/genderCode",
        #         "workers/person/genderSelfIdentityCode",
        #         "workers/person/highestEducationLevelCode",
        #         "workers/person/legalAddress",
        #         "workers/person/legalName",
        #         "workers/person/militaryClassificationCodes",
        #         "workers/person/militaryStatusCode",
        #         "workers/person/preferredName",
        #         "workers/person/raceCode",
        #         # "workers/person/governmentIDs",
        #     ]
        # ),
    }

    record = ADP_WFN.get(endpoint=f"hr/v2/workers/{aoid}", params=params)

    filepath = pathlib.Path(f"env/adp/{aoid}.json")

    filepath.parent.mkdir(parents=True, exist_ok=True)

    json.dump(obj=record.json(), fp=filepath.open(mode="w"))


def test_get_workers():
    params = {"asOfDate": "07/01/2024"}

    records = ADP_WFN.get_records(endpoint="hr/v2/workers", params=params)

    filepath = pathlib.Path("env/adp/workers.json")

    filepath.parent.mkdir(parents=True, exist_ok=True)

    json.dump(obj=records, fp=filepath.open(mode="w"))
