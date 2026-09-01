with
    enrollments as (
        select
            l.school_year_start,
            l.grade_canonical_name,
            l.promotion_status,
            l.assigned_school,
            l.enrollment_end_date,
            l.is_transfer_out,
            l.finalsite_enrollment_id,

            -- Finalsite emits pre-first-day `enrolled_date` values, which are
            -- contract or registration dates. Focus matches enrollment on the
            -- first attendance calendar date, so floor the start date up to the
            -- school year's first day, derived per school year from the Focus
            -- attendance calendar. Rows already on or after the first day, and
            -- years with no calendar, stay unchanged.
            greatest(
                l.enrollment_start_date,
                coalesce(fd.first_day_of_school, l.enrollment_start_date)
            ) as start_date,
        from {{ ref("int_finalsite__enrollment_lifecycle") }} as l
        left join
            {{ ref("int_focus__school_year_first_day") }} as fd
            on l.school_year_start = fd.syear
        -- Enrolled-only desired state, across all in-scope school years.
        -- Pre-enrollment statuses carry no `enrolled_date`, so they wait until
        -- Finalsite mints `enrollment_start_date`. A freshly enrolled student
        -- with no school assignment waits too, because Focus needs a school id.
        -- The kippmiami wrapper scopes this to the current academic year and
        -- reconciles it against live Focus.
        where l.enrollment_start_date is not null and l.assigned_school is not null
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus STUDENT_ENROLLMENT contract
select
    e.school_year_start as syear,

    sch.location_focus_school_id as school_id,

    ida.focus_student_id_prefixed as student_id,

    if(
        e.grade_canonical_name = 'k',
        'KG',
        -- non-digit grade names (e.g. pk) yield null here; Miami is K-9 today
        lpad(regexp_extract(e.grade_canonical_name, r'\d+'), 2, '0')
    ) as grade_id,

    format_date('%Y%m%d', e.start_date) as start_date,

    -- enrollment_code is the entry action and does not change on transfer_out;
    -- a withdrawal is expressed by drop_code + end_date, not by clearing the
    -- entry code.
    case when e.grade_canonical_name = 'k' then 'E05' else 'E01' end as enrollment_code,

    -- enrollment_end_date is gated to transfer_out upstream in
    -- int_finalsite__enrollment_lifecycle, so end_date needs no re-gating.
    format_date('%Y%m%d', e.enrollment_end_date) as end_date,

    cast(null as string) as calendar_id,
    cast(null as string) as prior_dist,
    cast(null as string) as prior_state,
    cast(null as string) as prior_country,
    cast(null as string) as ed_choice,
    cast(null as string) as stdt_dis_affect,
    cast(null as string) as offender_transfer_stdt,
    cast(null as string) as came_from,

    if(e.is_transfer_out, cca.withdrawal_school_txt, cast(null as string)) as moved_to,

    cast(null as string) as sec_sch,

    e.promotion_status as grde_prom_st,

    cast(null as string) as good_cause_exempt,
    cast(null as string) as graduation_requirement_program,
    cast(null as string) as next_school,
    cast(null as string) as next_grade,
    cast(null as string) as district_ood,
    cast(null as string) as sch_ood,
    cast(null as string) as include_in_class_rank,
    cast(null as int64) as fl_days_present,
    cast(null as int64) as fl_days_absent,
from enrollments as e
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on e.finalsite_enrollment_id = ida.finalsite_enrollment_id
    and ida.focus_student_id_prefixed is not null
left join
    {{ ref("int_finalsite__contact_custom_attributes") }} as cca
    on e.finalsite_enrollment_id = cca.finalsite_enrollment_id
left join
    {{ ref("int_people__location_crosswalk") }} as sch
    on e.assigned_school = sch.location_name
