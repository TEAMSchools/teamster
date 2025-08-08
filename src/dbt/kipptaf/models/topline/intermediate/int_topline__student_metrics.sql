with
    metrics_union_sid as (
        select
            'ADA Running' as metric_name,
            _dbt_source_relation,
            studentid,
            academic_year,
            schoolid,

            'Week' as term_type,
            week_start_monday as term_name,
            week_start_monday as term_start,
            week_end_sunday as term_end,

            attendancevalue_running as numerator,
            membershipvalue_running as denominator,
            ada_running as metric_value,
        from {{ ref("int_topline__ada_weekly_running") }}
    )

select
    co.academic_year,
    co.region,
    co.school_level,
    co.schoolid,
    co.school,
    co.student_number,
    co.state_studentnumber,
    co.student_name,
    co.grade_level,
    co.gender,
    co.ethnicity,
    co.iep_status,
    co.is_504,
    co.lep_status,
    co.gifted_and_talented,
    co.entrydate,
    co.exitdate,
    co.enroll_status,

    mu.metric_name,
    mu.term_type,
    mu.term_name,
    mu.term_start,
    mu.term_end,
    mu.numerator,
    mu.denominator,
    mu.metric_value,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    metrics_union_sid as mu
    on co.studentid = mu.studentid
    and co.schoolid = mu.schoolid
    and co.academic_year = mu.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="mu") }}
where co.academic_year >= {{ var("current_academic_year") - 1 }}
