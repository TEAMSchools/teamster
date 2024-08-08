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
    co.academic_year,
    co.lastfirst,
    co.advisor_lastfirst,
    co.student_number as ps_id,
    co.state_studentnumber as mdcps_id,
    co.gender,
    co.spedlep as iep_status,

    fp.fast_ela,
    fp.fast_math,

    gpa.cumulative_y1_gpa_unweighted as gpa,

  c.contact_1_name,
  c.contact_1_phone_home,
  c.contact_1_phone_mobile,
  c.contact_1_email_current,
  c.contact_2_name,
  c.contact_2_phone_home,
  c.contact_2_phone_mobile,
  c.contact_2_email_current,

from {{ ref("base_powerschool__student_enrollments") }} as co
left join
    fast_pivot as fp on co.academic_year - 1 = fp.academic_year and co.fleid = fp.fleid
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gpa
    on co.studentid = gpa.studentid
    and co.schoolid = gpa.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}

    left join {{ ref('int_powerschool__student_contacts_pivot') }} as c on c.student_id = co.student_id
where
    co.academic_year >= {{ var("current_academic_year") }} - 1
    and co.rn_year = 1
    and co.grade_level = 8
    and co.enroll_status = 0
    and co.region = 'Miami'
