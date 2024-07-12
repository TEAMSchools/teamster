with
    fast_concat as (
        select
            academic_year,
            student_id as fleid,
            assessment_subject as subject,
            assessment_grade,
            concat(achievement_level, ' (', scale_score, ')') as fast_score,
        from {{ ref("stg_fldoe__fast") }}
        where administration_window = 'PM3'
    ),
    fast_pivot as (
        select fleid, academic_year, elareading as fast_ela, mathematics as fast_math,
        from
            (select academic_year, fleid, subject, fast_score, from fast_concat)
            pivot (max(fast_score) for subject in ('ELAReading', 'Mathematics'))
    )
select
    co.lastfirst,
    co.advisor_lastfirst,
    co.student_number as ps_id,
    co.state_studentnumber as mdcps_id,
    co.gender,
    gpa.cumulative_y1_gpa_unweighted as gpa,
    fp.fast_ela,
    fp.fast_math,
    co.spedlep as iep_status
from {{ ref("base_powerschool__student_enrollments") }} as co
left join
    fast_pivot as fp on co.academic_year - 1 = fp.academic_year and co.fleid = fp.fleid
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gpa
    on co.studentid = gpa.studentid
    and co.schoolid = gpa.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.grade_level = 8
    and co.enroll_status = 0
    and co.region = 'Miami'
