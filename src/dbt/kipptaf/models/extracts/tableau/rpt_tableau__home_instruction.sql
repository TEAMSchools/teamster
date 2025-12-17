select
    co.student_number,
    co.state_studentnumber,
    co.student_name,
    co.academic_year,
    co.academic_year_display,
    co.school,
    co.region,
    co.grade_level,
    co.enroll_status,
    co.school_level,
    co.team as homeroom_section,
    co.advisor_lastfirst as homeroom_teacher_name,
    co.iep_status,
    co.ml_status,
    co.status_504,
    co.self_contained_status,

    dl.incident_id,
    dl.status,
    dl.reported_details,
    dl.admin_summary,
    dl.context,
    dl.infraction,
    dl.category,
    dl.home_instruction_reason,
    dl.final_approval,
    dl.instructor_source,
    dl.instructor_name,
    dl.board_approval_date,
    dl.hi_start_date,
    dl.hi_end_date,
    dl.create_lastfirst as referring_staff_name,
    dl.update_lastfirst as reviewing_staff_name,

    sp.enter_date_home_instruction as enter_date,
    sp.exit_date_home_instruction as exit_date,

    u.lastfirst as approver_name,

    cast(dl.hours_per_week as numeric) as hours_per_week,
    cast(dl.hourly_rate as numeric) as hourly_rate,

    concat('https://kippnj.deanslistsoftware.com/incidents/', dl.incident_id) as dl_url,

    date_diff(dl.hi_end_date, dl.hi_start_date, day) as n_days_dl,
    date_diff(
        sp.exit_date_home_instruction, sp.enter_date_home_instruction, day
    ) as n_days_ps,

    if(
        sp.enter_date_home_instruction is not null, true, false
    ) as is_logged_powerschool,

    if(sp.is_home_instruction = 1, true, false) as is_current,

    if(
        dl.approver_name is not null and dl.final_approval = 'Y', true, false
    ) as is_approved,

    if(
        dl.hi_start_date = sp.enter_date_home_instruction
        and dl.hi_end_date = sp.exit_date_home_instruction,
        true,
        false
    ) as is_date_aligned,

    if(
        sp.enter_date_home_instruction is null,
        null,
        concat(
            case
                when co.region = 'Newark'
                then 'https://psteam.kippnj.org/'
                when co.region = 'Camden'
                then 'https://pskcna.kippnj.org/'
                when co.region = 'Miami'
                then 'https://ps.kippmiami.org/'
            end,
            'admin/students/specialprograms.html?frn=00',
            co.students_dcid
        )
    ) as ps_url,

    (
        select countif(x is null),
        from
            unnest(
                [
                    cast(dl.final_approval as string),
                    cast(dl.instructor_source as string),
                    cast(dl.instructor_name as string),
                    cast(dl.hours_per_week as string),
                    cast(dl.hourly_rate as string),
                    cast(dl.board_approval_date as string),
                    cast(dl.hi_start_date as string),
                    cast(dl.hi_end_date as string),
                    cast(dl.approver_name as string)
                ]
            ) as x
    )
    = 0 as is_complete_dl,

    (
        select countif(x is null),
        from
            unnest(
                [
                    cast(dl.final_approval as string),
                    cast(dl.instructor_source as string),
                    cast(dl.instructor_name as string),
                    cast(dl.hours_per_week as string),
                    cast(dl.hourly_rate as string),
                    cast(dl.board_approval_date as string),
                    cast(dl.hi_start_date as string),
                    cast(dl.hi_end_date as string),
                    cast(dl.approver_name as string),
                    cast(sp.enter_date_home_instruction as string),
                    cast(sp.exit_date_home_instruction as string)
                ]
            ) as x
    )
    = 0 as is_complete_all,
from {{ ref("int_extracts__student_enrollments") }} as co
inner join
    {{ ref("int_deanslist__incidents") }} as dl
    on co.student_number = dl.student_school_id
    and co.academic_year = dl.create_ts_academic_year
    and (
        dl.home_instruction_reason is not null
        or dl.category = 'TX - HI Request (admin only)'
    )
    and dl.home_instruction_reason != '[Please select a reason]'
left join {{ ref("stg_deanslist__users") }} as u on dl.approver_name = u.dl_user_id
left join
    {{ ref("int_powerschool__spenrollments_pivot") }} as sp
    on co.studentid = sp.studentid
    and co.academic_year = sp.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sp") }}
    and dl.hi_start_date
    between sp.enter_date_home_instruction and sp.exit_date_home_instruction
    and {{ union_dataset_join_clause(left_alias="dl", right_alias="sp") }}
where co.grade_level != 99
