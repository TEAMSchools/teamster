with
    criteria as (
        select
            criterion_code,
            criterion_sort,
            gpa_band,
            criterion_label,
            required_type,
            type_label,
            urm_bar,
            required_count,
            requires_full_need,
            sets_aside_full_need,
        from unnest({{ early_application_criteria() }})
    ),

    submitted_colleges as (
        select
            _dbt_source_project,
            overgrad_student_id,
            university_id,
            application_type,

            any_value(university_name) as university_name,
            max(urm_graduation_rate) as urm_graduation_rate,
            logical_and(is_full_need) as is_full_need,
        from {{ ref("int_students__early_applications") }}
        where is_submitted and is_early
        group by
            _dbt_source_project, overgrad_student_id, university_id, application_type
    ),

    set_aside_bars as (
        select a.gpa_band, f.urm_bar,
        from criteria as a
        inner join criteria as f on a.gpa_band = f.gpa_band
        where a.sets_aside_full_need and f.requires_full_need
    ),

    full_need_set_aside as (
        select
            s._dbt_source_project,
            s.overgrad_student_id,

            b.gpa_band,

            min_by(s.university_id, s.university_name) as set_aside_university_id,
        from submitted_colleges as s
        inner join set_aside_bars as b on s.urm_graduation_rate >= b.urm_bar
        where s.is_full_need
        group by s._dbt_source_project, s.overgrad_student_id, b.gpa_band
    ),

    senior_criteria as (
        select
            r._dbt_source_project,
            r.overgrad_student_id,
            r.gpa_band,

            c.criterion_code,
            c.criterion_sort,
            c.criterion_label,
            c.required_type,
            c.type_label,
            c.urm_bar,
            c.required_count,
            c.requires_full_need,
            c.sets_aside_full_need,

            fa.set_aside_university_id,
        from {{ ref("int_students__early_applications_rollup") }} as r
        inner join criteria as c on r.gpa_band = c.gpa_band
        left join
            full_need_set_aside as fa
            on r.overgrad_student_id = fa.overgrad_student_id
            and r._dbt_source_project = fa._dbt_source_project
            and r.gpa_band = fa.gpa_band
    ),

    candidates as (
        select
            sc._dbt_source_project,
            sc.overgrad_student_id,
            sc.criterion_code,

            s.university_id,
            s.university_name,
            s.urm_graduation_rate,

            s.university_name
            || ' ('
            || s.application_type
            || ') '
            || format('%.1f%%', s.urm_graduation_rate) as college_label,

            if(
                sc.sets_aside_full_need
                and s.university_id = sc.set_aside_university_id,
                true,
                false
            ) as is_set_aside,

            if(
                s.urm_graduation_rate >= sc.urm_bar
                and (s.is_full_need or not sc.requires_full_need),
                true,
                false
            ) as meets_bar,

            -- a near-bar college is at most 5 points under the bar
            if(
                s.urm_graduation_rate >= sc.urm_bar - 5
                and s.urm_graduation_rate < sc.urm_bar,
                true,
                false
            ) as is_near_bar,
        from senior_criteria as sc
        inner join
            submitted_colleges as s
            on sc.overgrad_student_id = s.overgrad_student_id
            and sc._dbt_source_project = s._dbt_source_project
            and sc.required_type in ('any', s.application_type)
    ),

    qualifying as (
        select
            _dbt_source_project,
            overgrad_student_id,
            criterion_code,

            count(distinct university_id) as qualifying_count,

            string_agg(
                distinct college_label, ', ' order by college_label
            ) as qualifying_colleges,
        from candidates
        where meets_bar and not is_set_aside
        group by _dbt_source_project, overgrad_student_id, criterion_code
    ),

    near_bar as (
        select
            _dbt_source_project,
            overgrad_student_id,
            criterion_code,

            count(distinct university_id) as near_bar_count,
            max(urm_graduation_rate) as closest_rate,
            max_by(university_name, urm_graduation_rate) as closest_college,

            string_agg(
                distinct college_label, ', ' order by college_label
            ) as near_bar_colleges,
        from candidates
        where is_near_bar
        group by _dbt_source_project, overgrad_student_id, criterion_code
    ),

    counted as (
        select
            sc._dbt_source_project,
            sc.overgrad_student_id,
            sc.gpa_band,
            sc.criterion_code,
            sc.criterion_sort,
            sc.criterion_label,
            sc.type_label,
            sc.urm_bar,
            sc.required_count,

            q.qualifying_colleges,

            nb.near_bar_colleges,
            nb.closest_rate,
            nb.closest_college,

            coalesce(q.qualifying_count, 0) as qualifying_count,
            coalesce(nb.near_bar_count, 0) as near_bar_count,
        from senior_criteria as sc
        left join
            qualifying as q
            on sc.overgrad_student_id = q.overgrad_student_id
            and sc._dbt_source_project = q._dbt_source_project
            and sc.criterion_code = q.criterion_code
        left join
            near_bar as nb
            on sc.overgrad_student_id = nb.overgrad_student_id
            and sc._dbt_source_project = nb._dbt_source_project
            and sc.criterion_code = nb.criterion_code
    ),

    met as (
        select
            _dbt_source_project,
            overgrad_student_id,
            gpa_band,
            criterion_code,
            criterion_sort,
            criterion_label,
            type_label,
            urm_bar,
            required_count,
            qualifying_colleges,
            near_bar_colleges,
            closest_rate,
            closest_college,
            qualifying_count,
            near_bar_count,

            required_count - qualifying_count as colleges_short,

            if(qualifying_count >= required_count, true, false) as is_met,
        from counted
    ),

    near_miss as (
        select
            _dbt_source_project,
            overgrad_student_id,
            gpa_band,
            criterion_code,
            criterion_sort,
            criterion_label,
            type_label,
            urm_bar,
            required_count,
            qualifying_colleges,
            near_bar_colleges,
            closest_rate,
            closest_college,
            qualifying_count,
            near_bar_count,
            colleges_short,
            is_met,

            case
                when is_met
                then false
                when required_count = 1
                then near_bar_count >= 1
                when colleges_short = 1
                then true
                else near_bar_count >= colleges_short
            end as is_near_miss,
        from met
    )

select
    _dbt_source_project,
    overgrad_student_id,
    gpa_band,
    criterion_code,
    criterion_sort,
    criterion_label,
    required_count,
    urm_bar,
    qualifying_count,
    near_bar_count,
    is_met,
    is_near_miss,
    qualifying_colleges,
    near_bar_colleges,

    case
        when qualifying_colleges is not null and near_bar_colleges is not null
        then
            'Qualifying: '
            || qualifying_colleges
            || '; Near the bar: '
            || near_bar_colleges
        when qualifying_colleges is not null
        then 'Qualifying: ' || qualifying_colleges
        when near_bar_colleges is not null
        then 'Near the bar: ' || near_bar_colleges
    end as what_they_have,

    case
        when not is_near_miss
        then null
        when required_count = 1
        then
            format(
                'An %s college at %d%%+ (closest: %s at %.1f%%, %.1f points short)',
                type_label,
                urm_bar,
                closest_college,
                closest_rate,
                urm_bar - closest_rate
            )
        else
            format(
                '%d more %s %s at %d%%+',
                colleges_short,
                type_label,
                if(colleges_short = 1, 'college', 'colleges'),
                urm_bar
            )
    end as what_would_close_it,
from near_miss
