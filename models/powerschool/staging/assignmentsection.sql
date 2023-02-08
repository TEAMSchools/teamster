{%- set code_location = "kippcamden" -%}

{%- set source_name = model.fqn[1] -%}
{%- set model_name = this.identifier -%}

{{
    incremental_merge_source_file(
        source_name=source_name,
        model_name=model_name,
        file_uri=get_gcs_uri(
            code_location, source_name, model_name, var("partition_path")
        ),
        unique_key="assignmentsectionid",
        transform_cols=[
            {"name": "assignmentsectionid", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "sectionsdcid", "type": "int_value"},
            {"name": "assignmentid", "type": "int_value"},
            {"name": "relatedgradescaleitemdcid", "type": "int_value"},
            {"name": "scoreentrypoints", "type": "int_value"},
            {"name": "extracreditpoints", "type": "int_value"},
            {"name": "weight", "type": "int_value"},
            {"name": "totalpointvalue", "type": "int_value"},
            {"name": "iscountedinfinalgrade", "type": "int_value"},
            {"name": "isscoringneeded", "type": "int_value"},
            {"name": "publishdaysbeforedue", "type": "int_value"},
            {"name": "publishedscoretypeid", "type": "int_value"},
            {"name": "isscorespublish", "type": "int_value"},
            {"name": "maxretakeallowed", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
