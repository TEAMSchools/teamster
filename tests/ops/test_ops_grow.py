from dagster import build_op_context

from teamster.core.resources import BIGQUERY_RESOURCE
from teamster.libraries.google.bigquery.ops import BigQueryOpConfig, bigquery_query_op
from teamster.libraries.level_data.grow.ops import (
    grow_school_update_op,
    grow_user_update_op,
)


def test_grow_user_update_op():
    from teamster.code_locations.kipptaf.resources import GROW_RESOURCE

    context = build_op_context()

    users = bigquery_query_op(
        context=context,
        db_bigquery=BIGQUERY_RESOURCE,
        config=BigQueryOpConfig(
            dataset_id="kipptaf_extracts", table_id="rpt_schoolmint_grow__users"
        ),
    )

    grow_user_update_op(context=context, grow=GROW_RESOURCE, users=users)


def test_grow_school_update_op():
    from teamster.code_locations.kipptaf.resources import GROW_RESOURCE

    context = build_op_context()

    users = bigquery_query_op(
        context=context,
        db_bigquery=BIGQUERY_RESOURCE,
        config=BigQueryOpConfig(
            dataset_id="kipptaf_extracts", table_id="rpt_schoolmint_grow__users"
        ),
    )

    grow_school_update_op(context=context, grow=GROW_RESOURCE, users=users)
