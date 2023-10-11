with
    all_enrollments as (
        select
            id as studentid,
            schoolid,
            grade_level,
            entrydate,
            exitdate,
            exitcode,
            _dbt_source_relation,
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="entrydate", start_month=7, year_source="start"
                )
            }} as academic_year,
        from {{ ref("stg_powerschool__students") }}

        union all

        select
            studentid,
            schoolid,
            grade_level,
            entrydate,
            exitdate,
            exitcode,
            _dbt_source_relation,
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="entrydate", start_month=7, year_source="start"
                )
            }} as academic_year,
        from {{ ref("stg_powerschool__reenrollments") }}
    ),

    lags as (
        select
            studentid,
            academic_year,
            schoolid,
            grade_level,
            exitcode,
            _dbt_source_relation,
            lead(grade_level, 1) over (
                partition by studentid, _dbt_source_relation order by academic_year
            ) as next_gradelevel,
            lead(entrydate, 1) over (
                partition by studentid, _dbt_source_relation order by academic_year
            ) as next_entrydate,
            lead(exitdate, 1) over (
                partition by studentid, _dbt_source_relation order by academic_year
            ) as next_exitdate,
            lag(grade_level, 1) over (
                partition by studentid, _dbt_source_relation order by academic_year
            ) as prev_gradelevel,
            lag(exitcode, 1) over (
                partition by studentid, _dbt_source_relation order by academic_year
            ) as prev_exitcode,
        from all_enrollments
    )

select
    s.student_number,
    s.lastfirst,
    s.enroll_status,

    t.academic_year,
    t.schoolid,
    t.grade_level,
    t.exitcode,
    t.next_gradelevel,
    t.next_entrydate,
    t.next_exitdate,
    t.prev_gradelevel,
    t.prev_exitcode,

    'Promoted Next School - No Show' as audit_type,
from {{ ref("stg_powerschool__students") }} as s
inner join
    lags as t
    on s.id = t.studentid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="t") }}
where
    t.grade_level in (4, 8)
    and t.exitcode != 'G1'
    and t.next_gradelevel != 99
    and t.next_gradelevel > t.grade_level
    and t.next_exitdate <= t.next_entrydate

union all

select
    s.student_number,
    s.lastfirst,
    s.enroll_status,

    t.academic_year,
    t.schoolid,
    t.grade_level,
    t.exitcode,
    t.next_gradelevel,
    t.next_entrydate,
    t.next_exitdate,
    t.prev_gradelevel,
    t.prev_exitcode,
    case
        when t.prev_exitcode = 'T2'
        then 'Graduate - Transferred Exit Code'
        when t.prev_exitcode != 'G1'
        then 'Transferred - Graduated Enrollment Status'
        when t.next_gradelevel is null
        then 'Graduated - Transferred Enrollment Status'
        when t.next_gradelevel is not null
        then 'Graduated - Re-Enrolled'
    end as audit_type,
from {{ ref("stg_powerschool__students") }} as s
inner join
    lags as t
    on s.id = t.studentid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="t") }}
where t.grade_level = 99 and s.enroll_status != 3

union all

select
    s.student_number,
    s.lastfirst,
    s.enroll_status,

    t.academic_year,
    t.schoolid,
    t.grade_level,
    t.exitcode,
    t.next_gradelevel,
    t.next_entrydate,
    t.next_exitdate,
    t.prev_gradelevel,
    t.prev_exitcode,

    'No Show - Merge With Previous Record' as audit_type,
from {{ ref("stg_powerschool__students") }} as s
inner join
    lags as t
    on s.id = t.studentid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="t") }}
where t.next_entrydate = t.next_exitdate and t.next_gradelevel != 99
