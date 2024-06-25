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
    aoid = "G3ASWDTVJ0WV011W"

    r = ADP_WFN.get(endpoint=f"hr/v2/workers/{aoid}")

    print(json.dumps(r.json()))


def test_get_workers():
    params = {"asOfDate": "07/01/2022"}

    records = ADP_WFN.get_records(endpoint="hr/v2/workers", params=params)

    filepath = pathlib.Path("env/adp/workers.json")

    filepath.parent.mkdir(parents=True, exist_ok=True)

    json.dump(obj=records, fp=filepath.open(mode="w"))
