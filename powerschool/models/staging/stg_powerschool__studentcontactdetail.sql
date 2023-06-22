{{
    teamster_utils.generate_staging_model(
        unique_key="studentcontactdetailid.int_value",
        transform_cols=[
            {"name": "studentcontactdetailid", "extract": "int_value"},
            {"name": "studentcontactassocid", "extract": "int_value"},
            {"name": "relationshiptypecodesetid", "extract": "int_value"},
            {"name": "isactive", "extract": "int_value"},
            {"name": "isemergency", "extract": "int_value"},
            {"name": "iscustodial", "extract": "int_value"},
            {"name": "liveswithflg", "extract": "int_value"},
            {"name": "schoolpickupflg", "extract": "int_value"},
            {"name": "receivesmailflg", "extract": "int_value"},
            {"name": "excludefromstatereportingflg", "extract": "int_value"},
            {"name": "generalcommflag", "extract": "int_value"},
            {"name": "confidentialcommflag", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}

select *
from staging
