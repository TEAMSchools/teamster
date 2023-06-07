from dagster import EnvVar
from dagster_fivetran import FivetranResource, load_assets_from_fivetran_instance

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
    load_assets_from_fivetran_instance(
        fivetran=FivetranResource(
            api_key=EnvVar("FIVETRAN_API_KEY"),
            api_secret=EnvVar("FIVETRAN_API_SECRET"),
        ),
        connector_filter=lambda meta: meta.connector_id in FIVETRAN_CONNECTOR_IDS,
    )
