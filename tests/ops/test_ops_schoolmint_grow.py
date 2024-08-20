from dagster import build_op_context

from teamster.code_locations.kipptaf.resources import SCHOOLMINT_GROW_RESOURCE
from teamster.core.resources import BIGQUERY_RESOURCE
from teamster.libraries.google.bigquery.ops import (
    BigQueryGetTableOpConfig,
    bigquery_get_table_op,
)
from teamster.libraries.schoolmint.grow.ops import (
    schoolmint_grow_school_update_op,
    schoolmint_grow_user_update_op,
)


def test_schoolmint_grow_user_update_op():
    context = build_op_context()

    users = bigquery_get_table_op(
        context=context,
        db_bigquery=BIGQUERY_RESOURCE,
        config=BigQueryGetTableOpConfig(
            dataset_id="kipptaf_extracts", table_id="rpt_schoolmint_grow__users"
        ),
    )

    schoolmint_grow_user_update_op(
        context=context, schoolmint_grow=SCHOOLMINT_GROW_RESOURCE, users=users
    )


def test_schoolmint_grow_school_update_op():
    context = build_op_context()

    users = bigquery_get_table_op(
        context=context,
        db_bigquery=BIGQUERY_RESOURCE,
        config=BigQueryGetTableOpConfig(
            dataset_id="_dev_kipptaf_extracts", table_id="rpt_schoolmint_grow__users"
        ),
    )

    schoolmint_grow_school_update_op(
        context=context, schoolmint_grow=SCHOOLMINT_GROW_RESOURCE, users=users
    )
