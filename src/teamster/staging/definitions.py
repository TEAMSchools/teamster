from dagster import Definitions, load_assets_from_modules

from teamster.kipptaf import tableau

from . import assets, resources

defs = Definitions(
    assets=load_assets_from_modules(
        modules=[
            assets,
            tableau,
        ]
    ),
    resources={
        "tableau": resources.TABLEAU_SERVER_RESOURCE,
    },
)
