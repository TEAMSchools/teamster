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

    dli.student_id as dl_student_id,
    dli.incident_id as dl_id,
    dli.status,
    dli.reported_details,
    dli.admin_summary,
    dli.context,

    dli.create_ts_date as dl_timestamp,
    dli.infraction,

    cf.final_approval,
    cf.instructor_source,
    cf.instructor_name,
    cf.hours_per_week,
    cf.hourly_rate,
    cf.board_approval_date,
    cf.hi_start_date,
    cf.hi_end_date,

    concat(dli.create_first, ' ', dli.create_last) as referring_teacher_name,
    concat(dli.update_first, ' ', dli.update_last) as reviewed_by,
    concat(u.first_name, ' ', u.last_name) as `Approver Name`,

    coalesce(dli.category, 'Referral') as dl_behavior,
    cast(d.name as string) as term,
from {{ ref("stg_deanslist__incidents") }} as dli
left join
    {{ ref("int_deanslist__incidents__custom_fields__pivot") }} as cf
    on dli.incident_id = cf.incident_id
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="cf") }}
left join
    {{ ref("stg_deanslist__users") }} as u
    on cast(u.dl_user_id as string) = cf.approver_name
    and {{ union_dataset_join_clause(left_alias="u", right_alias="cf") }}
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on dli.student_school_id = co.student_number
    and dli.create_ts_academic_year = co.academic_year
    and {{ union_dataset_join_clause(left_alias="dli", right_alias="co") }}
    and co.rn_year = 1
inner join
    {{ ref("stg_reporting__terms") }} as d
    on co.schoolid = d.school_id
    and (cast(dli.create_ts_date as date) between d.start_date and d.end_date)
    and d.type = 'RT'
where
    dli.create_ts_academic_year = {{ var("current_academic_year") }}
    and (dli.category = 'TX - HI Request (admin only)' or cf.hi_start_date is not null)
