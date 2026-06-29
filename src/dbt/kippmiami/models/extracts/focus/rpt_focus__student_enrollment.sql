with
    desired as (
        select *, from {{ source("kipptaf_extracts", "rpt_focus__student_enrollment") }}
    ),

    decoded as (
        select d.*, dc.short_name as drop_code_decoded,
        from desired as d
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as dc
            on d.state_withdraw_label = dc.title
            and dc.type = 'Drop'
    ),

    matched as (
        select
            e.*,
            fe.enrollment_code as focus_enrollment_code,
            fe.drop_code as focus_drop_code,
            fe.end_date as focus_end_date,
        from decoded as e
        left join
            {{ ref("stg_focus__student_enrollment") }} as fe
            on cast(e.student_id as int64) = fe.student_id
            and e.start_date = format_date('%Y%m%d', fe.start_date)
        where
            fe.student_id is null
            or (
                e.end_date is not null
                and e.end_date is distinct from format_date('%Y%m%d', fe.end_date)
            )
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    syear,
    school_id,
    student_id,
    grade_id,
    start_date,
    if(
        focus_enrollment_code is null, enrollment_code, cast(null as string)
    ) as enrollment_code,
    end_date,
    if(focus_drop_code is null, drop_code_decoded, cast(null as string)) as drop_code,
    calendar_id,
    prior_dist,
    prior_state,
    prior_country,
    ed_choice,
    stdt_dis_affect,
    offender_transfer_stdt,
    came_from,
    moved_to,
    sec_sch,
    grde_prom_st,
    good_cause_exempt,
    graduation_requirement_program,
    next_school,
    next_grade,
    district_ood,
    sch_ood,
    include_in_class_rank,
    fl_days_present,
    fl_days_absent,
from matched
