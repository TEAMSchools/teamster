{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "studentid", "extract": "int_value"},
            {"name": "sectionid", "extract": "int_value"},
            {"name": "termid", "extract": "int_value"},
            {"name": "percent", "extract": "double_value"},
            {"name": "absences", "extract": "double_value"},
            {"name": "tardies", "extract": "double_value"},
            {"name": "potentialcrhrs", "extract": "double_value"},
            {"name": "earnedcrhrs", "extract": "double_value"},
            {"name": "grade_level", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "excludefromgpa", "extract": "int_value"},
            {"name": "gpa_points", "extract": "double_value"},
            {"name": "gpa_addedvalue", "extract": "double_value"},
            {"name": "gpa_custom2", "extract": "double_value"},
            {"name": "excludefromclassrank", "extract": "int_value"},
            {"name": "excludefromhonorroll", "extract": "int_value"},
            {"name": "isearnedcrhrsfromgb", "extract": "int_value"},
            {"name": "ispotentialcrhrsfromgb", "extract": "int_value"},
            {"name": "excludefromtranscripts", "extract": "int_value"},
            {"name": "replaced_dcid", "extract": "int_value"},
            {"name": "excludefromgraduation", "extract": "int_value"},
            {"name": "excludefromgradesuppression", "extract": "int_value"},
            {"name": "gradereplacementpolicy_id", "extract": "int_value"},
            {"name": "whomodifiedid", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}

select
    *,
    left(storecode, 2) as storecode_type,
    cast(left(cast(termid as string), 2) as int) as yearid,
    cast(left(cast(termid as string), 2) as int) + 1990 as academic_year,
    cast(left(cast(termid as string), 2) as int) + 1991 as fiscal_year,
from staging
