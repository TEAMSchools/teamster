with
    fast_concat as (
        select
            _dbt_source_relation,
            academic_year,
            student_id,
            assessment_subject,
            assessment_grade,

            concat(achievement_level, ' (', scale_score, ')') as fast_score,
        from {{ ref("stg_fldoe__fast") }}
        where administration_window = 'PM3'
    ),

    fast_pivot as (
        select _dbt_source_relation, student_id, academic_year, fast_ela, fast_math,
        from
            fast_concat pivot (
                max(fast_score) for assessment_subject
                in ('English Language Arts' as fast_ela, 'Mathematics' as fast_math)
            )
    )

select
    co.academic_year,
    co.lastfirst,
    co.advisor_lastfirst,
    co.student_number as ps_id,
    co.state_studentnumber as mdcps_id,
    co.gender,
    co.spedlep as iep_status,
    co.contact_1_name,
    co.contact_1_phone_home,
    co.contact_1_phone_mobile,
    co.contact_1_email_current,
    co.contact_2_name,
    co.contact_2_phone_home,
    co.contact_2_phone_mobile,
    co.contact_2_email_current,
    co.enroll_status,
    co.grade_level,

    fp.fast_ela,
    fp.fast_math,

    gpa.cumulative_y1_gpa_unweighted as gpa,

    round(co.ada_unweighted_year_prev, 2) as previous_year_ada,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    fast_pivot as fp
    on co.fleid = fp.student_id
    and co.academic_year = (fp.academic_year + 1)
    and {{ union_dataset_join_clause(left_alias="co", right_alias="fp") }}
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gpa
    on co.studentid = gpa.studentid
    and co.schoolid = gpa.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
where
    co.rn_year = 1
    and co.region = 'Miami'
    and co.grade_level in (7, 8)
    and co.academic_year >= {{ var("current_academic_year") - 1 }}
