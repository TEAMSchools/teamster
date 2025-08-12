select
    co.student_number,
    co.state_studentnumber,
    co.lastfirst,
    co.academic_year,
    co.school_abbreviation,
    co.grade_level,
    co.advisory_name as team,
    co.advisor_lastfirst as advisor_name,
    co.spedlep as iep_status,
    co.gender,
    co.ethnicity,
    co.region,

    d.name as term,

    dli.student_id as dl_student_id,
    dli.incident_id as dl_id,
    dli.status,
    dli.reported_details,
    dli.admin_summary,
    dli.context,
    dli.create_ts_date as dl_timestamp,
    dli.infraction,
    dli.final_approval,
    dli.instructor_source,
    dli.instructor_name,
    dli.hours_per_week,
    dli.hourly_rate,
    dli.board_approval_date,
    dli.hi_start_date,
    dli.hi_end_date,

    u.full_name as approver_name,

    concat(dli.create_first, ' ', dli.create_last) as referring_teacher_name,
    concat(dli.update_first, ' ', dli.update_last) as reviewed_by,

    coalesce(dli.category, 'Referral') as dl_behavior,
from {{ ref("int_extracts__student_enrollments") }} as co
inner join
    {{ ref("int_deanslist__incidents") }} as dli
    on co.student_number = dli.student_school_id
    and co.academic_year = dli.create_ts_academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="dli") }}
    and (dli.category = 'TX - HI Request (admin only)' or dli.hi_start_date is not null)
inner join
    {{ ref("stg_reporting__terms") }} as d
    on co.schoolid = d.school_id
    and dli.create_ts_date between d.start_date and d.end_date
    and d.type = 'RT'
left join
    {{ ref("stg_deanslist__users") }} as u
    on dli.approver_name = u.dl_user_id_str
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="cf") }}
where co.academic_year = {{ var("current_academic_year") }} co.rn_year = 1
