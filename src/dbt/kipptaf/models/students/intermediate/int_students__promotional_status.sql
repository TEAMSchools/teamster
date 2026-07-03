with
    metrics as (select *, from {{ ref("int_students__promotional_status_metrics") }}),

    policies as (
        select *, from {{ ref("stg_google_sheets__reporting__promo_status_policies") }}
    ),

    metrics_long as (
        select
            student_number,
            academic_year,
            term_name,
            region,
            grade_level,
            metric,
            metric_value,
        from
            (
                select
                    student_number,
                    academic_year,
                    term_name,
                    region,
                    grade_level,

                    {% for m in promo_status_metric_columns() %}
                        cast({{ m }} as float64) as {{ m }},
                    {% endfor %}
                from metrics
            -- trunk-ignore(sqlfluff/LT01)
            ) unpivot include nulls(
                metric_value for metric in (
                    {% for m in promo_status_metric_columns() %}
                        {{ m }}{% if not loop.last %},{% endif %}
                    {% endfor %}
                )
            )
    ),

    conditions as (
        select
            mtr.student_number,
            mtr.academic_year,
            mtr.term_name,

            p.domain,
            p.grade_min,
            p.grade_max,
            p.rule_group,
            p.detail_label,

            p.term_name as policy_term_name,

            case
                when mtr.metric_value is null
                then p.if_missing = 'met'
                when p.comparator = 'less_than'
                then mtr.metric_value < p.`value`
                when p.comparator = 'less_than_or_equal'
                then mtr.metric_value <= p.`value`
                when p.comparator = 'greater_than'
                then mtr.metric_value > p.`value`
                when p.comparator = 'greater_than_or_equal'
                then mtr.metric_value >= p.`value`
                when p.comparator = 'equals'
                then mtr.metric_value = p.`value`
                when p.comparator = 'not_equals'
                then mtr.metric_value != p.`value`
            end as is_met,
        from metrics_long as mtr
        inner join
            policies as p
            on mtr.academic_year = p.academic_year
            and mtr.region = p.region
            and mtr.metric = p.metric
            and mtr.grade_level between p.grade_min and p.grade_max
            and (mtr.term_name = p.term_name or p.term_name = 'All')
            and p.domain in ('attendance', 'academic')
    ),

    rule_groups as (
        select
            student_number,
            academic_year,
            term_name,
            domain,
            grade_min,
            grade_max,
            policy_term_name,
            rule_group,

            logical_and(is_met) as is_fired,
            max(detail_label) as detail_label,
        from conditions
        group by
            student_number,
            academic_year,
            term_name,
            domain,
            grade_min,
            grade_max,
            policy_term_name,
            rule_group
    ),

    domain_status as (
        select
            student_number,
            academic_year,
            term_name,
            domain,

            logical_or(is_fired) as is_off_track,

            array_agg(
                if(is_fired, detail_label, null) ignore nulls
                order by rule_group
                limit 1
            )[safe_offset(0)] as detail_label,
        from rule_groups
        group by student_number, academic_year, term_name, domain
    ),

    domain_wide as (
        select
            student_number,
            academic_year,
            term_name,

            logical_or(
                if(domain = 'attendance', is_off_track, null)
            ) as is_off_track_attendance,

            logical_or(
                if(domain = 'academic', is_off_track, null)
            ) as is_off_track_academic,

            max(
                if(domain = 'attendance', detail_label, null)
            ) as attendance_detail_label,
        from domain_status
        group by student_number, academic_year, term_name
    ),

    overall_metrics_long as (
        select
            student_number,
            academic_year,
            term_name,
            region,
            grade_level,
            metric,
            metric_value,
        from metrics_long

        union all

        select
            m.student_number,
            m.academic_year,
            m.term_name,
            m.region,
            m.grade_level,

            pseudo_metric as metric,

            if(
                pseudo_metric = 'is_off_track_attendance',
                cast(cast(dw.is_off_track_attendance as int) as float64),
                cast(cast(dw.is_off_track_academic as int) as float64)
            ) as metric_value,
        from metrics as m
        cross join
            unnest(
                ['is_off_track_attendance', 'is_off_track_academic']
            ) as pseudo_metric
        left join
            domain_wide as dw
            on m.student_number = dw.student_number
            and m.academic_year = dw.academic_year
            and m.term_name = dw.term_name
    ),

    overall_conditions as (
        select
            mtr.student_number,
            mtr.academic_year,
            mtr.term_name,

            p.grade_min,
            p.grade_max,
            p.rule_group,

            p.term_name as policy_term_name,

            case
                when mtr.metric_value is null
                then p.if_missing = 'met'
                when p.comparator = 'less_than'
                then mtr.metric_value < p.`value`
                when p.comparator = 'less_than_or_equal'
                then mtr.metric_value <= p.`value`
                when p.comparator = 'greater_than'
                then mtr.metric_value > p.`value`
                when p.comparator = 'greater_than_or_equal'
                then mtr.metric_value >= p.`value`
                when p.comparator = 'equals'
                then mtr.metric_value = p.`value`
                when p.comparator = 'not_equals'
                then mtr.metric_value != p.`value`
            end as is_met,
        from overall_metrics_long as mtr
        inner join
            policies as p
            on mtr.academic_year = p.academic_year
            and mtr.region = p.region
            and mtr.metric = p.metric
            and mtr.grade_level between p.grade_min and p.grade_max
            and (mtr.term_name = p.term_name or p.term_name = 'All')
            and p.domain = 'overall'
    ),

    overall_rule_groups as (
        select
            student_number,
            academic_year,
            term_name,
            grade_min,
            grade_max,
            policy_term_name,
            rule_group,

            logical_and(is_met) as is_fired,
        from overall_conditions
        group by
            student_number,
            academic_year,
            term_name,
            grade_min,
            grade_max,
            policy_term_name,
            rule_group
    ),

    overall_status as (
        select
            student_number,
            academic_year,
            term_name,

            logical_or(is_fired) as is_off_track,
        from overall_rule_groups
        group by student_number, academic_year, term_name
    )

select
    m.student_number,
    m.academic_year,
    m.term_name,
    m.is_current,
    m.ada_term_running,
    m.n_absences_y1_running,
    m.n_absences_y1_running_non_susp,
    m.n_absences_y1_running_non_susp_no_tardy,
    m.iready_reading_recent,
    m.iready_math_recent,
    m.n_failing,
    m.n_failing_core,
    m.projected_credits_cum,
    m.projected_credits_y1_term,
    m.dibels_composite_level_recent_str,
    m.exemption,
    m.manual_retention,

    m.dibels_composite_level as dibels_composite_level_recent,
    m.star_math_level as star_math_level_recent,
    m.star_ela_level as star_reading_level_recent,
    m.fast_ela_level as fast_ela_level_recent,
    m.fast_math_level as fast_math_level_recent,

    coalesce(
        dw.attendance_detail_label,
        case
            dw.is_off_track_attendance
            when true
            then 'Off-Track'
            when false
            then 'On-Track'
        end
    ) as attendance_status_hs_detail,

    case
        dw.is_off_track_attendance when true then 'Off-Track' when false then 'On-Track'
    end as attendance_status,

    case
        dw.is_off_track_academic when true then 'Off-Track' when false then 'On-Track'
    end as academic_status,

    case
        os.is_off_track when true then 'Off-Track' when false then 'On-Track'
    end as overall_status,
from metrics as m
left join
    domain_wide as dw
    on m.student_number = dw.student_number
    and m.academic_year = dw.academic_year
    and m.term_name = dw.term_name
left join
    overall_status as os
    on m.student_number = os.student_number
    and m.academic_year = os.academic_year
    and m.term_name = os.term_name
