with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__ps_attendance_daily",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__ps_attendance_daily",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__ps_attendance_daily",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__ps_attendance_daily",
                    ),
                ]
            )
        }}
    )

select
    *,

    {{ date_to_fiscal_year(date_field="att_date", start_month=7, year_source="start") }}
    as academic_year,
from union_relations
