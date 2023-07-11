from dagster import EnvVar, build_resources

from teamster.core.adp.resources import AdpWorkforceNowResource


def test_resource():
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
        adp_wfn: AdpWorkforceNowResource = resources.adp_wfn

        r = adp_wfn._request(
            method="GET",
            url=f"{adp_wfn._service_root}/core/v1/event-notification-messages",
        )

        print(r.json())
