with
    admissions as (
        select
            _dbt_source_project,
            id,
            student__id,
            university__id,
            university_name,
            due_date__type,
            status,

            cast(university__ipeds_id as string) as ipeds_id_string,
            cast(due_date__date as date) as due_date,
            cast(updated_at as timestamp) as updated_at,

            if(
                due_date__type in (
                    'early_action',
                    'early_action_2',
                    'early_decision',
                    'early_decision_2',
                    'single_choice_early_action'
                ),
                true,
                false
            ) as is_early,
        from {{ ref("int_overgrad__admissions") }}
    ),

    admissions_scoped as (
        select
            _dbt_source_project,
            id,
            student__id,
            university__id,
            university_name,
            due_date__type,
            status,
            ipeds_id_string,
            due_date,
            updated_at,
            is_early,

            -- missing deadline types stay so the tracker can flag them
            if(is_early or due_date__type is null, true, false) as is_in_scope,
        from admissions
    ),

    college_rate_range as (
        -- a college can have 2 Salesforce accounts; collapse to 1 row per IPEDS id
        select
            nces_id,

            min(adjusted_6_year_minority_graduation_rate) as min_rate,
            max(adjusted_6_year_minority_graduation_rate) as max_rate,
        from {{ ref("stg_kippadb__account") }}
        where nces_id is not null
        group by nces_id
    ),

    college_rates as (
        select
            nces_id,

            -- accounts that disagree get no rate, so the college never counts
            if(min_rate != max_rate, null, max_rate) as urm_graduation_rate,

            if(min_rate != max_rate, true, false) as has_conflicting_rate,
        from college_rate_range
    )

select
    a._dbt_source_project,
    a.id as admission_id,
    a.student__id as overgrad_student_id,
    a.university__id as university_id,
    a.university_name,
    a.due_date__type as due_date_type,
    a.status as application_status,
    a.due_date,
    a.updated_at,
    a.is_early,

    cr.urm_graduation_rate,

    -- TODO(#6194): placeholder until a meets-full-need source is chosen
    true as is_full_need,

    coalesce(cr.has_conflicting_rate, false) as has_conflicting_rate,

    -- Applied and every later status; Will Apply, Withdrew, Did Not Apply are not
    if(
        a.status
        in ('Applied', 'Accepted', 'Denied', 'Deferred', 'Waitlisted', 'Enrolled'),
        true,
        false
    ) as is_submitted,

    case
        when a.due_date__type in ('early_decision', 'early_decision_2')
        then 'ED'
        when a.is_early
        then 'EA'
    end as application_type,
from admissions_scoped as a
left join college_rates as cr on a.ipeds_id_string = cr.nces_id
where a.is_in_scope
