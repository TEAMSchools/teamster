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
        unique_key="studentcontactdetailid",
        transform_cols=[
            {"name": "studentcontactdetailid", "type": "int_value"},
            {"name": "studentcontactassocid", "type": "int_value"},
            {"name": "relationshiptypecodesetid", "type": "int_value"},
            {"name": "isactive", "type": "int_value"},
            {"name": "isemergency", "type": "int_value"},
            {"name": "iscustodial", "type": "int_value"},
            {"name": "liveswithflg", "type": "int_value"},
            {"name": "schoolpickupflg", "type": "int_value"},
            {"name": "receivesmailflg", "type": "int_value"},
            {"name": "excludefromstatereportingflg", "type": "int_value"},
            {"name": "generalcommflag", "type": "int_value"},
            {"name": "confidentialcommflag", "type": "int_value"},
        ],
    )
}}
