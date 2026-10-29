with
    seniors as (
        select
            _dbt_source_project,
            id as overgrad_student_id,
            school__name as high_school,
            is_ed_ea,
            first_name,
            last_name,
            assigned_counselor__first_name,
            assigned_counselor__last_name,

            cast(academics__unweighted_gpa as numeric) as unweighted_gpa_numeric,
            cast(updated_at as timestamp) as updated_at,
        from {{ ref("int_overgrad__students") }}
        where
            graduation_year = {{ var("current_academic_year") + 1 }}
            -- the 3 KIPP high schools the tracker reports on
            and school__name in (
                'KIPP Cooper Norcross High School',
                'KIPP Newark Collegiate Academy',
                'KIPP Newark Lab High School'
            )
    ),

    seniors_rounded as (
        select
            _dbt_source_project,
            overgrad_student_id,
            high_school,
            is_ed_ea,
            first_name,
            last_name,
            assigned_counselor__first_name,
            assigned_counselor__last_name,
            updated_at,

            round(unweighted_gpa_numeric, 2) as unweighted_gpa,
        from seniors
    ),

    application_labels as (
        select
            _dbt_source_project,
            overgrad_student_id,
            university_id,
            application_status,
            is_submitted,
            due_date,
            updated_at,

            university_name || ' (' || application_type || ')' as application_label,

            cast(round(urm_graduation_rate) as int64) as urm_rounded,
        from {{ ref("int_students__early_applications") }}
    ),

    submitted_labels as (
        select
            _dbt_source_project,
            overgrad_student_id,
            university_id,

            application_label
            || ' '
            || coalesce(format('%d%%', urm_rounded), 'no rate') as submitted_label,
        from application_labels
        where is_submitted
    ),

    submitted as (
        select
            _dbt_source_project,
            overgrad_student_id,

            count(distinct university_id) as submitted_early_count,

            string_agg(
                distinct submitted_label, ', ' order by submitted_label
            ) as submitted_early_applications,
        from submitted_labels
        group by _dbt_source_project, overgrad_student_id
    ),

    will_apply as (
        select
            _dbt_source_project,
            overgrad_student_id,

            min(due_date) as earliest_will_apply_due_date,

            string_agg(
                distinct application_label, ', ' order by application_label
            ) as will_apply_early_applications,
        from application_labels
        where application_status = 'Will Apply'
        group by _dbt_source_project, overgrad_student_id
    ),

    latest_application as (
        select
            _dbt_source_project,
            overgrad_student_id,

            max(updated_at) as latest_application_updated_at,
        from application_labels
        group by _dbt_source_project, overgrad_student_id
    )

select
    s._dbt_source_project,
    s.overgrad_student_id,
    s.high_school,
    s.unweighted_gpa,

    sub.submitted_early_applications,

    wa.will_apply_early_applications,
    wa.earliest_will_apply_due_date,

    s.last_name || ', ' || s.first_name as student_name,
    s.assigned_counselor__first_name
    || ' '
    || s.assigned_counselor__last_name as counselor_name,

    coalesce(sub.submitted_early_count, 0) as submitted_early_count,

    (
        select max(t),
        from unnest([s.updated_at, la.latest_application_updated_at]) as t
    ) as latest_overgrad_updated_at,

    if(s.is_ed_ea = 'Yes', true, false) as is_ed_ea_flagged,

    case
        when s.unweighted_gpa >= 3.75
        then '3.75+'
        when s.unweighted_gpa >= 3.50
        then '3.50-3.74'
        when s.unweighted_gpa >= 3.00
        then '3.00-3.49'
        when s.unweighted_gpa is not null
        then 'Below 3.00'
        else 'No GPA'
    end as gpa_band,
from seniors_rounded as s
left join
    submitted as sub
    on s.overgrad_student_id = sub.overgrad_student_id
    and s._dbt_source_project = sub._dbt_source_project
left join
    will_apply as wa
    on s.overgrad_student_id = wa.overgrad_student_id
    and s._dbt_source_project = wa._dbt_source_project
left join
    latest_application as la
    on s.overgrad_student_id = la.overgrad_student_id
    and s._dbt_source_project = la._dbt_source_project
