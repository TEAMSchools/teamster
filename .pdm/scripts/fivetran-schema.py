import argparse
import json
import pathlib

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
regency_carrying  # facebook_pages
muskiness_cumulative  # instagram_business
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

        schemas = instance.make_request(
            method="GET", endpoint=f"connectors/{connector_id}/schemas"
        )

    filepath = pathlib.Path(f"env/fivetran/schema/{connector_id}.json")

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open(mode="w+") as fp:
        json.dump(obj=schemas, fp=fp)


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("connector_id")

    main(args.parse_args())
