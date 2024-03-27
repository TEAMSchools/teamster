{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "sectionid", "extract": "int_value"},
            {"name": "studentid", "extract": "int_value"},
            {"name": "percent", "extract": "double_value"},
            {"name": "points", "extract": "double_value"},
            {"name": "pointspossible", "extract": "double_value"},
            {"name": "varcredit", "extract": "double_value"},
            {"name": "gradebooktype", "extract": "int_value"},
            {"name": "calculatedpercent", "extract": "double_value"},
            {"name": "isincomplete", "extract": "int_value"},
            {"name": "isexempt", "extract": "int_value"},
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

grade_fix as (
    select
        * except (grade, citizenship, comment_value, `percent`),

        nullif(grade, '--') as grade,
        nullif(citizenship, '') as citizenship,
        nullif(comment_value, '') as comment_value,

        if(grade = '--', null, `percent`) as `percent`,
    from staging
),

with_percent_decimal as (select *, `percent` / 100.0 as percent_decimal, from grade_fix)

select
    *,
    if(percent_decimal < 0.5, 0.5, percent_decimal) as percent_decimal_adjusted,
    if(percent_decimal < 0.5, 'F*', grade) as grade_adjusted,
from with_percent_decimal
