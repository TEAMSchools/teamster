with
    enrollments as (
        select
            student_number,
            _dbt_source_project,
            _dbt_source_relation,
            schoolid,
            entrydate,
            exitdate,
            academic_year,
            enroll_status,
            grade_level,
        from {{ ref("int_powerschool__student_enrollment_union") }}
    ),

    calendar_days as (
        select schoolid, date_value, _dbt_source_relation,
        from {{ ref("stg_powerschool__calendar_day") }}
        where insession = 1 and date_value is not null
    ),

    year_terms as (
        select
            schoolid,
            firstday,
            lastday,
            _dbt_source_relation,

            yearid + 1990 as academic_year,
        from {{ ref("stg_powerschool__terms") }}
        where isyearrec = 1
    ),

    expanded as (
        select
            enr.student_number,
            enr._dbt_source_project,
            enr.schoolid,
            enr.entrydate,
            enr.enroll_status,
            enr.grade_level,

            enr.academic_year as stint_academic_year,

            cd.date_value as date_key,

            yt.academic_year as term_academic_year,

            {{ extract_code_location("enr") }} as code_location,
        from enrollments as enr
        inner join
            calendar_days as cd
            on enr.schoolid = cd.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="cd") }}
            and enr.entrydate <= cd.date_value
            and enr.exitdate > cd.date_value
        inner join
            year_terms as yt
            on cd.schoolid = yt.schoolid
            and {{ union_dataset_join_clause(left_alias="cd", right_alias="yt") }}
            and cd.date_value between yt.firstday and yt.lastday
    )

select
    sch.location_key,

    e.date_key,
    e.term_academic_year as academic_year,
    e.grade_level,
    e.enroll_status,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "e.student_number",
                "e._dbt_source_project",
                "e.date_key",
            ]
        )
    }} as student_enrollment_daily_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "e.student_number",
                "e._dbt_source_project",
                "e.stint_academic_year",
                "e.entrydate",
            ]
        )
    }} as student_enrollment_key,

    {{ dbt_utils.generate_surrogate_key(["e.student_number"]) }} as student_key,

    1 as is_enrolled,

    cast(
        e.date_key = least(
            max(e.date_key) over (
                partition by e.schoolid, e.code_location, e.term_academic_year
            ),
            current_date('{{ var("local_timezone") }}')
        ) as int64
    ) as is_current_record,

    cast(
        e.date_key = least(
            max(e.date_key) over (
                partition by
                    e.schoolid,
                    e.code_location,
                    e.term_academic_year,
                    date_trunc(e.date_key, month)
            ),
            current_date('{{ var("local_timezone") }}')
        ) as int64
    ) as is_month_end_record,

    cast(
        e.date_key = least(
            max(e.date_key) over (
                partition by
                    e.schoolid,
                    e.code_location,
                    e.term_academic_year,
                    -- trunk-ignore(sqlfluff/LT01): week(monday) special syntax
                    date_trunc(e.date_key, week(monday))
            ),
            current_date('{{ var("local_timezone") }}')
        ) as int64
    ) as is_week_end_record,

    row_number() over (
        partition by e.student_number, e._dbt_source_project, e.term_academic_year
        order by e.date_key desc
    )
    = 1 as is_latest_record,
from expanded as e
left join
    {{ ref("stg_powerschool__schools") }} as sch
    on e.schoolid = sch.school_number
    and e._dbt_source_project = sch._dbt_source_project
