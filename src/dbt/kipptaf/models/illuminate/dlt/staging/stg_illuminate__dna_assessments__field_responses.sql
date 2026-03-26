{{
    dbt_utils.deduplicate(
        relation=source("illuminate_dna_assessments", "field_responses"),
        partition_by="field_id, response_id, version_id",
        order_by="field_response_id desc",
    )
}}
