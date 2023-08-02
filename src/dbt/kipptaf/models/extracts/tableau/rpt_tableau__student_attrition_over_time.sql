{{ config(enabled=False) }}

with
    attrition_dates as (
        select
            date_day,
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="date_day", start_month=10, year_source="start"
                )
            }} as attrition_year,
        from {{ ref("utils__date_spine") }}
    )

select
    y1.student_number,
    y1.lastfirst,
    y1.academic_year as `year`,
    y1.school_level,
    y1.reporting_schoolid,
    y1.grade_level,
    y1.entrydate,
    y1.exitdate as y1_exitdate,
    regexp_extract(y1._dbt_source_relation, r'(kipp\w+)_') as db_name,

    s.exitdate,
    s.exitcode,
    s.exitcomment,

    d.date_day as `date`,

    y2.entrydate as y2_entrydate,

    case
        /* graduates != attrition */
        when y1.exitcode = 'G1'
        then 0.0
        /* handles re-enrollments during the school year */
        when s.exitdate >= y1.exitdate and s.exitdate >= d.date_day
        then 0.0
        /* was not enrolled on 10/1 next year */
        when y1.exitdate <= d.date_day and y2.entrydate is null
        then 1.0
        else 0.0
    end as is_attrition,
from {{ ref("base_powerschool__student_enrollments") }} as y1
inner join
    {{ ref("stg_powerschool__students") }} as s
    on y1.student_number = s.student_number
    and {{ union_dataset_join_clause(left_alias="y1", right_alias="s") }}
left join
    {{ ref("base_powerschool__student_enrollments") }} as y2
    on y1.student_number = y2.student_number
    and y1.academic_year = (y2.academic_year - 1)
    and date(y2.academic_year, 10, 1) between y2.entrydate and y2.exitdate
    and {{ union_dataset_join_clause(left_alias="y1", right_alias="y2") }}
inner join
    attrition_dates as d
    on y1.academic_year = d.attrition_year
    and d.date_day <= current_datetime("America/New_York")
where date(y1.academic_year, 10, 1) between y1.entrydate and y1.exitdate
