{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
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
