from dagster import build_op_context

from teamster.libraries.google.bigquery.ops import BigQueryOpConfig, bigquery_query_op
from teamster.libraries.zendesk.ops import zendesk_user_sync_op


def test_zendesk_user_sync_op():
    from teamster.core.resources import BIGQUERY_RESOURCE, ZENDESK_RESOURCE

    with build_op_context() as context:
        users = bigquery_query_op(
            context=context,
            db_bigquery=BIGQUERY_RESOURCE,
            config=BigQueryOpConfig(
                query="""
                    select
                        email,
                        name,
                        suspended,
                        external_id,
                    from kipptaf_extracts.rpt_zendesk__users
                """
            ),
        )

        output = zendesk_user_sync_op(
            context=context, zendesk=ZENDESK_RESOURCE, users=users
        )

        for o in output:
            context.log.info(o)
