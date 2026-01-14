from dagster import JsonMetadataValue, materialize
from dagster_shared import check


def test_tableau_teacher_gradebook_group_sync():
    from teamster.code_locations.kipptaf.resources import TABLEAU_SERVER_RESOURCE
    from teamster.code_locations.kipptaf.tableau.assets import (
        tableau_teacher_gradebook_group_sync,
    )
    from teamster.core.resources import BIGQUERY_RESOURCE

    result = materialize(
        assets=[tableau_teacher_gradebook_group_sync],
        resources={
            "db_bigquery": BIGQUERY_RESOURCE,
            "tableau": TABLEAU_SERVER_RESOURCE,
        },
    )

    assert result.success

    errors = check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("errors"),
        ttype=JsonMetadataValue,
    )

    assert isinstance(errors.value, list)
    assert len(errors.value) == 0
