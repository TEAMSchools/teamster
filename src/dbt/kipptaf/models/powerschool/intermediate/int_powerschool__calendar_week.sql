with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool", "int_powerschool__calendar_week"
                    ),
                    source(
                        "kippcamden_powerschool", "int_powerschool__calendar_week"
                    ),
                    source("kippmiami_powerschool", "int_powerschool__calendar_week"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    *,
    initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
    case
        when
            academic_year = {{ var("current_academic_year") }}
            and current_date('America/New_York')
            between week_start_monday and week_end_sunday
        then true
        when
            week_start_monday
            = max(week_start_monday) over (partition by academic_year, schoolid)
        then true
        else false
    end as is_current_week_mon_sun,
from union_relations
