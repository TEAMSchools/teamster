with
    fast_concat as (
        select
            _dbt_source_relation,
            academic_year,
            student_id as fleid,
            assessment_subject as `subject`,
            assessment_grade,
            concat(achievement_level, ' (', scale_score, ')') as fast_score,
        from {{ ref("stg_fldoe__fast") }}
        where administration_window = 'PM3'
    ),

    fast_pivot as (
        select _dbt_source_relation, fleid, academic_year, fast_ela, fast_math,
        from
            fast_concat pivot (
                max(fast_score) for `subject`
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

    fp.fast_ela,
    fp.fast_math,

    gpa.cumulative_y1_gpa_unweighted as gpa,

    round(ada.ada, 2) as previous_year_ada,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join
    fast_pivot as fp
    on co.fleid = fp.fleid
    and co.academic_year - 1 = fp.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="fp") }}
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gpa
    on co.studentid = gpa.studentid
    and co.schoolid = gpa.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
left join
    {{ ref("int_powerschool__ada") }} as ada
    on co.studentid = ada.studentid
    and co.yearid = ada.yearid + 1
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ada") }}
where
    co.academic_year >= {{ var("current_academic_year") }} - 1
    and co.rn_year = 1
    and co.grade_level = 8
    and co.region = 'Miami'
