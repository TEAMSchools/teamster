from dagster import JsonMetadataValue, materialize
from dagster_shared import check


def test_teacher_gradebook_email_group_update():
    from teamster.code_locations.kipptaf.resources import TABLEAU_SERVER_RESOURCE
    from teamster.code_locations.kipptaf.tableau.assets import (
        teacher_gradebook_email_group_update,
    )
    from teamster.core.resources import BIGQUERY_RESOURCE

    result = materialize(
        assets=[teacher_gradebook_email_group_update],
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
