import os

from dagster_fivetran import FivetranResource

from teamster.core.fivetran.resources import load_assets_from_fivetran_instance
from teamster.kipptaf import CODE_LOCATION

FIVETRAN_CONNECTOR_IDS = [
    "philosophical_overbite",  # zendesk
    "jinx_credulous",  # illuminate
    "repay_spelled",  # kippadb
    "bellows_curliness",  # coupa
    "genuine_describing",  # illuminate_xmin
    "aspirate_uttering",  # hubspot
    "sameness_cunning",  # adp_workforce_now
]

assets = load_assets_from_fivetran_instance(
    fivetran=FivetranResource(
        api_key=os.getenv("FIVETRAN_API_KEY"),
        api_secret=os.getenv("FIVETRAN_API_SECRET"),
    ),
    key_prefix=[CODE_LOCATION],
    connector_filter=(lambda meta: meta.connector_id in FIVETRAN_CONNECTOR_IDS),
    connector_files=[
        f"src/teamster/core/fivetran/schema/{connector_id}.pickle"
        for connector_id in FIVETRAN_CONNECTOR_IDS
    ],
)

__all__ = [
    assets,
]
