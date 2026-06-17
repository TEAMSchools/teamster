-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    l.school_year_start as syear,
    sch.location_focus_school_id as school_id,
    -- STDT_ID is null until the Finalsite-minted student id lands in
    -- id_attributes; repoint to int_finalsite__contact_id_attributes then.
    cast(null as string) as student_id,
    if(
        l.grade_canonical_name = 'k',
        'KG',
        lpad(regexp_extract(l.grade_canonical_name, r'\d+'), 2, '0')
    ) as grade_id,
    format_date('%Y%m%d', l.enrollment_start_date) as start_date,
    ec.focus_enrollment_code as enrollment_code,
    if(
        l.lifecycle_action = 'transfer_out',
        format_date('%Y%m%d', l.enrollment_end_date),
        cast(null as string)
    ) as end_date,
    if(
        l.lifecycle_action = 'transfer_out', dc.focus_drop_code, cast(null as string)
    ) as drop_code,
    cast(null as string) as calendar_id,
    cast(null as string) as prior_dist,
    cast(null as string) as prior_state,
    cast(null as string) as prior_country,
    cast(null as string) as ed_choice,
    cast(null as string) as stdt_dis_affect,
    cast(null as string) as offender_transfer_stdt,
    cast(null as string) as came_from,
    cast(null as string) as moved_to,
    cast(null as string) as sec_sch,
    cast(null as string) as grde_prom_st,
    cast(null as string) as good_cause_exempt,
    cast(null as string) as graduation_requirement_program,
    cast(null as string) as next_school,
    cast(null as string) as next_grade,
    cast(null as string) as district_ood,
    cast(null as string) as sch_ood,
    cast(null as string) as include_in_class_rank,
    cast(null as int64) as fl_days_present,
    cast(null as int64) as fl_days_absent,
    cast(null as int64) as fl_days_absent_not_disc,
from {{ ref("int_finalsite__enrollment_lifecycle") }} as l
left join
    {{ ref("int_people__location_crosswalk") }} as sch
    on l.assigned_school = sch.location_name
left join
    {{ ref("stg_google_sheets__focus__enrollment_code_crosswalk") }} as ec
    on l.lifecycle_action = ec.finalsite_lifecycle_action
left join
    {{ ref("stg_google_sheets__focus__drop_code_crosswalk") }} as dc
    on l.withdrawal_reason = dc.finalsite_withdrawal_reason
