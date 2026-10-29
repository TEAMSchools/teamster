with
    early_admissions as (
        select
            _dbt_source_project,
            id,
            student__id,
            university__id,
            university_name,
            due_date__type,
            status,

            cast(university__ipeds_id as string) as university_ipeds_id,
            cast(due_date__date as date) as due_date,
            cast(updated_at as timestamp) as updated_at,
        from {{ ref("int_overgrad__admissions") }}
        where
            due_date__type in (
                'early_action',
                'early_action_2',
                'early_decision',
                'early_decision_2',
                'single_choice_early_action'
            )
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

    acc.adjusted_6_year_minority_graduation_rate as urm_graduation_rate,

    -- TODO(#6190): placeholder until a meets-full-need source is chosen
    true as is_full_need,

    if(
        a.due_date__type in ('early_decision', 'early_decision_2'), 'ED', 'EA'
    ) as application_type,

    if(
        a.status
        in ('Applied', 'Accepted', 'Denied', 'Deferred', 'Waitlisted', 'Enrolled'),
        true,
        false
    ) as is_submitted,
from early_admissions as a
left join
    {{ ref("stg_kippadb__account") }} as acc on a.university_ipeds_id = acc.nces_id
