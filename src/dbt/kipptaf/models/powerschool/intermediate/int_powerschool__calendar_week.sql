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
                    source(
                        "kipppaterson_powerschool", "int_powerschool__calendar_week"
                    ),
                ]
            )
        }}
    )

select
    *,

    initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

    {# TODO: move to powerschool package #}
    case
        when
            academic_year = {{ var("current_academic_year") }}
            and current_date('{{ var("local_timezone") }}')
            between week_start_monday and week_end_sunday
        then true
        when
            week_start_monday = max(week_start_monday) over (
                partition by _dbt_source_relation, schoolid, academic_year
            )
        then true
        else false
    end as is_current_week_mon_sun,

    min(week_start_monday) over (
        partition by _dbt_source_relation, schoolid, academic_year
    ) as first_day_school_year,
from union_relations
