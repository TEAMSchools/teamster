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

            -- Finalsite emits pre-first-day enrolled_dates (contract/registration
            -- dates); Focus matches enrollment on the first attendance calendar
            -- date, so floor the start date up to the school year's first day
            -- (derived per school year from the Focus attendance calendar). Rows
            -- already on/after the first day, and years with no calendar, are
            -- left unchanged.
            greatest(
                l.enrollment_start_date,
                coalesce(fd.first_day_of_school, l.enrollment_start_date)
            ) as start_date,
        from {{ ref("int_finalsite__enrollment_lifecycle") }} as l
        left join
            {{ ref("int_focus__school_year_first_day") }} as fd
            on l.school_year_start = fd.syear
        -- enrolled-only: pre-enrollment statuses (enrollment_in_progress,
        -- assigned_school) carry no enrolled_date; Focus enrollment records
        -- require an entry date, so defer these students until Finalsite mints
        -- enrollment_start_date. See #4291.
        where l.enrollment_start_date is not null
    ),

    -- Enrollments already loaded into Focus, deduped to one row per
    -- (student_id, syear, start_date) so the anti-join below cannot fan out.
    -- has_drop_code / has_end_date flag whether Focus has already recorded an
    -- exit for that enrollment.
    focus_enrollments as (
        select
            cast(student_id as string) as focus_student_id,
            syear as focus_syear,
            start_date as focus_start_date,

            logical_or(drop_code is not null) as has_drop_code,
            logical_or(end_date is not null) as has_end_date,
        from {{ source("kippmiami_dlt_focus", "student_enrollment") }}
        group by student_id, syear, start_date
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

    -- Focus import header is drop_code; this carries the raw Finalsite withdraw
    -- label, which the kippmiami reconciliation layer decodes to the Focus
    -- short_name. fl_state_withdraw_codes_ss is a raw contact custom attribute
    -- (NOT gated upstream), so gate it to transfer_out here — a withdraw code is
    -- only meaningful for a withdrawal, and an ungated value would emit a drop
    -- code for a still-enrolled student downstream.
    if(
        e.is_transfer_out, cca.fl_state_withdraw_codes_ss, cast(null as string)
    ) as drop_code,

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
left join
    focus_enrollments as fe
    on ida.focus_student_id_prefixed = fe.focus_student_id
    and e.school_year_start = fe.focus_syear
    and e.start_date = fe.focus_start_date
-- delta feed: suppress rows Focus already holds identically. Keep a row when it
-- is absent from Focus (new enrollment), or when it carries an exit the matched
-- Focus row has not recorded. end_date and drop_code are gated independently:
-- drop_code is a raw Finalsite custom attribute not tied to enrollment_end_date,
-- so the two exit fields can arrive in separate runs — a drop_code that lands
-- after Focus already has the end_date (or vice versa) must still sync.
-- school_id / grade_id / enrollment_code are import codes translated by Focus on
-- load, so they are not comparable and are not used to detect changes.
where
    fe.focus_student_id is null
    or (e.enrollment_end_date is not null and not fe.has_end_date)
    or (
        e.is_transfer_out
        and cca.fl_state_withdraw_codes_ss is not null
        and not fe.has_drop_code
    )
