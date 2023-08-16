from dagster import EnvVar, build_resources

from teamster.core.adp.resources import AdpWorkforceNowResource

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
    aoid = "G3MQ5XDMH0DC9TWJ"

    r = ADP_WFN._request(
        method="GET", url=f"{ADP_WFN._service_root}/hr/v2/workers/{aoid}"
    )

    print(r.json())


def test_get_workers():
    r = ADP_WFN._request(method="GET", url=f"{ADP_WFN._service_root}/hr/v2/workers")

    workers = r.json()["workers"]

    print([w for w in workers if w["associateOID"] == "G3MQ5XDMH0DC9TWJ"])
