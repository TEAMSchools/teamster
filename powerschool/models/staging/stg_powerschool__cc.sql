{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "studentid", "extract": "int_value"},
            {"name": "sectionid", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "termid", "extract": "int_value"},
            {"name": "attendance_type_code", "extract": "int_value"},
            {"name": "unused2", "extract": "int_value"},
            {"name": "currentabsences", "extract": "int_value"},
            {"name": "currenttardies", "extract": "int_value"},
            {"name": "teacherid", "extract": "int_value"},
            {"name": "origsectionid", "extract": "int_value"},
            {"name": "unused3", "extract": "int_value"},
            {"name": "studyear", "extract": "int_value"},
            {"name": "whomodifiedid", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}},

calcs as (
    select
        *,
        abs(termid) as abs_termid,
        abs(sectionid) as abs_sectionid,
        safe_cast(left(safe_cast(abs(termid) as string), 2) as int) as yearid,
    from staging
)

select *, (yearid + 1990) as academic_year, (yearid + 1991) as fiscal_year,
from calcs
