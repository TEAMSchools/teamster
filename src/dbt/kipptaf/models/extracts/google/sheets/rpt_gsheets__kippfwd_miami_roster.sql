with
    fast_concat as (
        select
            _dbt_source_relation,
            student_id,
            academic_year,

            concat(achievement_level, ' (', scale_score, ')') as fast_score,
            lower(concat(discipline, '_', administration_window)) as pivot_column,
        from {{ ref("stg_fldoe__fast") }}
    ),

    fast_pivot as (
        /* TODO: Add prev-year PM3 */
        select
            _dbt_source_relation,
            student_id,
            academic_year,
            ela_pm1,
            ela_pm2,
            ela_pm3,
            math_pm1,
            math_pm2,
            math_pm3,
        from
            fast_concat pivot (
                max(fast_score) for pivot_column
                in ('ela_pm1', 'ela_pm2', 'ela_pm3', 'math_pm1', 'math_pm2', 'math_pm3')
            )
    ),

    gpa_term as (
        select yearid, schoolid, studentid, _dbt_source_relation, gpa_y1,
        from {{ ref("int_powerschool__gpa_term") }}
        where is_current
    )

select
    co.academic_year,
    co.student_name as lastfirst,
    co.advisor_lastfirst,
    co.student_number as ps_id,
    co.secondary_state_studentnumber as mdcps_id,
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

    fp.ela_pm1,
    fp.ela_pm2,
    fp.ela_pm3,
    fp.math_pm1,
    fp.math_pm2,
    fp.math_pm3,

    co.cumulative_y1_gpa_unweighted as gpa_cumulative,
    co.ada_unweighted_year_prev as previous_year_ada,
    co.state_studentnumber as fleid,

    gpa.gpa_y1,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    fast_pivot as fp
    on co.state_studentnumber = fp.student_id
    and co.academic_year = fp.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="fp") }}
left join
    {{ ref("int_powerschool__gpa_term") }} as gpa
    on co.studentid = gpa.studentid
    and co.yearid = gpa.yearid
    and co.schoolid = gpa.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
where
    co.rn_year = 1
    and co.region = 'Miami'
    and co.grade_level in (7, 8)
    and co.academic_year >= {{ var("current_academic_year") - 1 }}
