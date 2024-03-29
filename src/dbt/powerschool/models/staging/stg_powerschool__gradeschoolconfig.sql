{{
    teamster_utils.generate_staging_model(
        unique_key="gradeschoolconfigid.int_value",
        transform_cols=[
            {"name": "gradeschoolconfigid", "extract": "int_value"},
            {"name": "schoolsdcid", "extract": "int_value"},
            {"name": "yearid", "extract": "int_value"},
            {"name": "defaultdecimalcount", "extract": "int_value"},
            {"name": "iscalcformulaeditable", "extract": "int_value"},
            {"name": "isdropscoreeditable", "extract": "int_value"},
            {"name": "iscalcprecisioneditable", "extract": "int_value"},
            {"name": "iscalcmetriceditable", "extract": "int_value"},
            {"name": "isrecentscoreeditable", "extract": "int_value"},
            {"name": "ishigherstndautocalc", "extract": "int_value"},
            {"name": "ishigherstndcalceditable", "extract": "int_value"},
            {"name": "ishighstandardeditable", "extract": "int_value"},
            {"name": "iscalcmetricschooledit", "extract": "int_value"},
            {"name": "isstandardsshown", "extract": "int_value"},
            {"name": "isstandardsshownonasgmt", "extract": "int_value"},
            {"name": "istraditionalgradeshown", "extract": "int_value"},
            {"name": "iscitizenshipdisplayed", "extract": "int_value"},
            {"name": "termbinlockoffset", "extract": "int_value"},
            {"name": "lockwarningoffset", "extract": "int_value"},
            {"name": "issectstndweighteditable", "extract": "int_value"},
            {"name": "minimumassignmentvalue", "extract": "int_value"},
            {"name": "isgradescaleteachereditable", "extract": "int_value"},
            {"name": "isstandardslimited", "extract": "int_value"},
            {"name": "isstandardslimitededitable", "extract": "int_value"},
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
