from dagster import EnvVar, build_resources
from dagster_fivetran import (
    FivetranResource,
    asset_defs,
    load_assets_from_fivetran_instance,
)

FIVETRAN_CONNECTOR_IDS = [
    "philosophical_overbite",  # zendesk
    "jinx_credulous",  # illuminate
    "repay_spelled",  # kippadb
    "bellows_curliness",  # coupa
    "genuine_describing",  # illuminate_xmin
    "aspirate_uttering",  # hubspot
    "sameness_cunning",  # adp_workforce_now
]


def test_resource():
    with build_resources(
        resources={
            "fivetran": FivetranResource(
                api_key=EnvVar("FIVETRAN_API_KEY"),
                api_secret=EnvVar("FIVETRAN_API_SECRET"),
            )
        }
    ) as resources:
        instance: asset_defs.FivetranInstanceCacheableAssetsDefinition = (
            load_assets_from_fivetran_instance(
                fivetran=resources.fivetran,
                connector_filter=lambda meta: meta.connector_id
                in FIVETRAN_CONNECTOR_IDS,
            )
        )

        output_connectors: list[asset_defs.FivetranConnectionMetadata] = []

        groups = instance._fivetran_instance.make_request("GET", "groups")["items"]

        for group in groups:
            print(group)
            group_id = group["id"]

            connectors = instance._fivetran_instance.make_request(
                "GET", f"groups/{group_id}/connectors"
            )["items"]
            for connector in connectors:
                print(connector)
                connector_id = connector["id"]

                connector_name = connector["schema"]

                setup_state = connector.get("status", {}).get("setup_state")
                if setup_state and setup_state in ("incomplete", "broken"):
                    continue

                connector_url = asset_defs.get_fivetran_connector_url(connector)

                schemas = instance._fivetran_instance.make_request(
                    "GET", f"connectors/{connector_id}/schemas"
                )

                output_connectors.append(
                    asset_defs.FivetranConnectionMetadata(
                        name=connector_name,
                        connector_id=connector_id,
                        connector_url=connector_url,
                        schemas=schemas,
                    )
                )
