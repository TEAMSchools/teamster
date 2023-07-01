import argparse
import json

from dagster import EnvVar, build_resources
from dagster_fivetran import FivetranResource

"""
drab_headwear  # kipptaf

sameness_cunning  # adp_workforce_now
aspirate_uttering  # hubspot
bellows_curliness  # coupa
philosophical_overbite  # zendesk
repay_spelled  # kippadb
genuine_describing  # illuminate_xmin
jinx_credulous  # illuminate
"""


def main(args):
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

        connector = instance.make_request(
            method="GET", endpoint=f"connectors/{connector_id}"
        )

        schemas = instance.make_request(
            method="GET", endpoint=f"connectors/{connector_id}/schemas"
        )

    connector_name = connector["schema"]

    destination_tables = []
    for service_name, schema in schemas["schemas"].items():
        schema_name = schema["name_in_destination"]

        for table_type, table in schema["tables"].items():
            table_name = table["name_in_destination"]

            if table["enabled"]:
                destination_tables.append(f"{schema_name}.{table_name}")

        del schema

    del schemas

    with open(
        file=f"src/teamster/{args.code_location}/fivetran/schema/{connector_id}.json",
        mode="w",
    ) as fp:
        json.dump(
            obj={
                "group_name": connector_name,
                "connector_id": connector_id,
                "destination_tables": destination_tables,
            },
            fp=fp,
        )


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("code_location")
    args.add_argument("connector_id")

    main(args.parse_args())
