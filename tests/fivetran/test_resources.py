import json

from dagster import EnvVar, build_resources
from dagster_fivetran import FivetranResource

from teamster.core.fivetran.resources import (
    FivetranInstanceCacheableAssetsDefinition,
    load_assets_from_fivetran_instance,
)

FIVETRAN_CONNECTOR_IDS = [
    "aspirate_uttering",  # hubspot
    "bellows_curliness",  # coupa
    "genuine_describing",  # illuminate_xmin
    "jinx_credulous",  # illuminate
    "philosophical_overbite",  # zendesk
    "repay_spelled",  # kippadb
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
        instance: FivetranInstanceCacheableAssetsDefinition = (
            load_assets_from_fivetran_instance(
                fivetran=resources.fivetran,
                connector_filter=(
                    lambda meta: meta.connector_id in FIVETRAN_CONNECTOR_IDS
                ),
                schema_files=[
                    "src/teamster/core/fivetran/schema/jinx_credulous.json",
                    "src/teamster/core/fivetran/schema/genuine_describing.json",
                ],
            )
        )

        connectors = instance._get_connectors()

        # for connector in connectors:
        #     print(connectors)
        #     with open(
        #         f"src/teamster/core/fivetran/schema/{connector.connector_id}.json", "w"
        #     ) as fp:
        #         json.dump(obj=connector.schemas, fp=fp)
