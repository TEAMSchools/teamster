{{
    teamster_utils.generate_staging_model(
        unique_key="gradesectionconfigid.int_value",
        transform_cols=[
            {"name": "gradesectionconfigid", "extract": "int_value"},
            {"name": "sectionsdcid", "extract": "int_value"},
            {"name": "gradeformulasetid", "extract": "int_value"},
            {"name": "defaultdecimalcount", "extract": "int_value"},
            {"name": "iscalcformulaeditable", "extract": "int_value"},
            {"name": "isdropscoreeditable", "extract": "int_value"},
            {"name": "iscalcprecisioneditable", "extract": "int_value"},
            {"name": "isstndcalcmeteditable", "extract": "int_value"},
            {"name": "isstndrcntscoreeditable", "extract": "int_value"},
            {"name": "ishigherlvlstndeditable", "extract": "int_value"},
            {"name": "ishigherstndautocalc", "extract": "int_value"},
            {"name": "ishigherstndcalceditable", "extract": "int_value"},
            {"name": "iscalcsectionfromstndedit", "extract": "int_value"},
            {"name": "issectstndweighteditable", "extract": "int_value"},
            {"name": "minimumassignmentvalue", "extract": "int_value"},
            {"name": "isgradescaleteachereditable", "extract": "int_value"},
            {"name": "isusingpercentforstndautocalc", "extract": "int_value"},
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
