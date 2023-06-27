import argparse
import json
import pickle

from dagster import EnvVar, build_resources
from dagster_fivetran import FivetranResource
from dagster_fivetran.asset_defs import FivetranConnectionMetadata
from dagster_fivetran.utils import get_fivetran_connector_url

"""
"sameness_cunning"  # adp_workforce_now
"aspirate_uttering"  # hubspot
"bellows_curliness"  # coupa
"philosophical_overbite"  # zendesk
"repay_spelled"  # kippadb
"genuine_describing"  # illuminate_xmin
"jinx_credulous"  # illuminate
"""


def main(args):
    group_id = args.group_id
    connector_id = args.connector_id

    with build_resources(
        resources={
            "fivetran": FivetranResource(
                api_key=EnvVar("FIVETRAN_API_KEY"),
                api_secret=EnvVar("FIVETRAN_API_SECRET"),
            )
        }
    ) as resources:
        instance: FivetranResource = resources.fivetran

        groups = instance.make_request("GET", f"groups/{group_id}/connectors")["items"]
        # print(groups)

        connector = [conn for conn in groups if conn["id"] == connector_id][0]
        # print(connector)

        if args.schema:
            with open(file=args.schema, mode="r") as fp:
                schemas = json.load(fp=fp)
        else:
            schemas = instance.make_request("GET", f"connectors/{connector_id}/schemas")
        # print(schemas)

    metadata = FivetranConnectionMetadata(
        name=connector["schema"],
        connector_id=connector_id,
        connector_url=get_fivetran_connector_url(connector),
        schemas=schemas,
    )
    # print(metadata)

    with open(
        file=f"src/teamster/core/fivetran/schema/{connector_id}.pickle", mode="wb"
    ) as fp:
        pickle.dump(obj=metadata, file=fp)


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("group_id")
    args.add_argument("connector_id")
    args.add_argument("--schema")

    main(args.parse_args())
