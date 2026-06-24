-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    l.school_year_start as syear,

    sch.location_focus_school_id as school_id,

    ida.focus_student_id as student_id,

    if(
        l.grade_canonical_name = 'k',
        'KG',
        lpad(regexp_extract(l.grade_canonical_name, r'\d+'), 2, '0')
    ) as grade_id,

    format_date('%Y%m%d', l.enrollment_start_date) as start_date,

    ec.focus_enrollment_code as enrollment_code,

    -- enrollment_end_date / withdrawal_reason are already null upstream for
    -- non-transfer rows, so no transfer_out re-gating is needed here.
    format_date('%Y%m%d', l.enrollment_end_date) as end_date,

    dc.focus_drop_code as drop_code,

    cast(null as string) as calendar_id,
    cast(null as string) as prior_dist,
    cast(null as string) as prior_state,
    cast(null as string) as prior_country,
    cast(null as string) as ed_choice,
    cast(null as string) as stdt_dis_affect,
    cast(null as string) as offender_transfer_stdt,
    cast(null as string) as came_from,

    cca.withdrawal_school_txt as moved_to,

    cast(null as string) as sec_sch,

    l.promotion_status as grde_prom_st,

    cast(null as string) as good_cause_exempt,
    cast(null as string) as graduation_requirement_program,
    cast(null as string) as next_school,
    cast(null as string) as next_grade,
    cast(null as string) as district_ood,
    cast(null as string) as sch_ood,
    cast(null as string) as include_in_class_rank,
    cast(null as int64) as fl_days_present,
    cast(null as int64) as fl_days_absent,
from {{ ref("int_finalsite__enrollment_lifecycle") }} as l
left join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on l.finalsite_enrollment_id = ida.finalsite_enrollment_id
left join
    {{ ref("int_finalsite__contact_custom_attributes") }} as cca
    on l.finalsite_enrollment_id = cca.finalsite_enrollment_id
left join
    {{ ref("int_people__location_crosswalk") }} as sch
    on l.assigned_school = sch.location_name
left join
    {{ ref("stg_google_sheets__focus__enrollment_code_crosswalk") }} as ec
    on l.lifecycle_action = ec.finalsite_lifecycle_action
left join
    {{ ref("stg_google_sheets__focus__drop_code_crosswalk") }} as dc
    on l.withdrawal_reason = dc.finalsite_withdrawal_reason
