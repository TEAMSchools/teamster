from dagster import define_asset_job


def foo(asset_selection):
    define_asset_job(
        name="survey_metadata_asset_job",
        selection=asset_selection,
        partitions_def=...,
    )
