with
    agg_by_school as (
        select
            student_school_id,
            create_ts_academic_year,
            school_id,

            count(
                distinct if(is_suspension, incident_penalty_id, null)
            ) as suspension_count_all,
        from {{ ref("int_deanslist__incidents__penalties") }}
        where referral_tier not in ('Non-Behavioral', 'Social Work')
        group by student_school_id, create_ts_academic_year, school_id
    ),

    student_level as (
        select
            co.academic_year,
            co.academic_year_display,
            co.region,
            co.school,
            co.iep_status,
            co.lep_status,
            co.grade_level,

            if(ag.suspension_count_all > 0, 1, 0) as is_suspended_all_y1_int,
        from {{ ref("int_extracts__student_enrollments") }} as co
        left join
            agg_by_school as ag
            on co.student_number = ag.student_school_id
            and co.academic_year = ag.create_ts_academic_year
            and co.deanslist_school_id = ag.school_id
        where co.academic_year >= 2019 and co.grade_level != 99
    )

select
    academic_year,
    academic_year_display,
    null as region,
    null as school,
    null as grade_level,
    'org' as level,
    round(avg(is_suspended_all_y1_int), 2) as pct_suspended_all_y1,
    round(
        avg(if(iep_status = 'Has IEP', is_suspended_all_y1_int, null)), 2
    ) as pct_suspended_iep_y1,
    round(
        avg(if(lep_status, is_suspended_all_y1_int, null)), 2
    ) as pct_suspended_lep_y1,
from student_level
group by academic_year, academic_year_display

union all

select
    academic_year,
    academic_year_display,
    region,
    null as school,
    null as grade_level,
    'region' as level,
    round(avg(is_suspended_all_y1_int), 2) as pct_suspended_all_y1,
    round(
        avg(if(iep_status = 'Has IEP', is_suspended_all_y1_int, null)), 2
    ) as pct_suspended_iep_y1,
    round(
        avg(if(lep_status, is_suspended_all_y1_int, null)), 2
    ) as pct_suspended_lep_y1,
from student_level
group by academic_year, academic_year_display, region

union all

select
    academic_year,
    academic_year_display,
    region,
    school,
    null as grade_level,
    'school' as level,
    round(avg(is_suspended_all_y1_int), 2) as pct_suspended_all_y1,
    round(
        avg(if(iep_status = 'Has IEP', is_suspended_all_y1_int, null)), 2
    ) as pct_suspended_iep_y1,
    round(
        avg(if(lep_status, is_suspended_all_y1_int, null)), 2
    ) as pct_suspended_lep_y1,
from student_level
group by academic_year, academic_year_display, region, school

union all

select
    academic_year,
    academic_year_display,
    region,
    school,
    grade_level,
    'grade' as level,
    round(avg(is_suspended_all_y1_int), 2) as pct_suspended_all_y1,
    round(
        avg(if(iep_status = 'Has IEP', is_suspended_all_y1_int, null)), 2
    ) as pct_suspended_iep_y1,
    round(
        avg(if(lep_status, is_suspended_all_y1_int, null)), 2
    ) as pct_suspended_lep_y1,
from student_level
group by academic_year, academic_year_display, region, school, grade_level
