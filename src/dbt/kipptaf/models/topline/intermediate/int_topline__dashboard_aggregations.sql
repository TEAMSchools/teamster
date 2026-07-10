with
    student_metrics as (
        select
            academic_year,
            region,
            schoolid,
            school,
            grade_level,
            layer,
            indicator,
            discipline,
            term,
            term_end,
            is_current_week,
            numerator,
            denominator,
            metric_value,

            'week' as period_type,

            format_date('%G-W%V', term) as period_label,
        from {{ ref("int_topline__student_metrics") }}
    ),

    student_metrics_periods as (
        select
            academic_year,
            region,
            schoolid,
            school,
            grade_level,
            layer,
            indicator,
            discipline,
            term,
            term_end,
            period_type,
            period_label,
            numerator,
            denominator,
            metric_value,
        from {{ ref("int_topline__student_metrics_periods") }}
    ),

    student_metrics_all as (
        select
            academic_year,
            region,
            schoolid,
            school,
            grade_level,
            layer,
            indicator,
            discipline,
            term,
            term_end,
            is_current_week,
            period_type,
            period_label,
            numerator,
            denominator,
            metric_value,
        from student_metrics

        union all

        select
            academic_year,
            region,
            schoolid,
            school,
            grade_level,
            layer,
            indicator,
            discipline,
            term,
            term_end,

            cast(null as boolean) as is_current_week,

            period_type,
            period_label,
            numerator,
            denominator,
            metric_value,
        from student_metrics_periods
    ),

    pre_agg_union_student as (
        select
            m.academic_year,
            m.region,
            m.schoolid,
            m.school,
            m.layer,
            m.indicator,
            m.discipline,
            m.term,
            m.term_end,
            m.is_current_week,
            m.period_type,
            m.period_label,

            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal,

            case
                g.aggregation_type
                when 'Average'
                then round(avg(m.metric_value), 3)
                when 'Divide'
                then round(safe_divide(sum(m.numerator), sum(m.denominator)), 3)
                when 'Sum'
                then round(sum(m.metric_value), 0)
            end as metric_aggregate_value,
        from student_metrics_all as m
        left join
            {{ ref("int_google_sheets__topline_aggregate_goals") }} as g
            on m.region = g.entity
            and m.schoolid = g.schoolid
            and m.grade_level between g.grade_low and g.grade_high
            and m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'school'
        group by
            m.academic_year,
            m.region,
            m.schoolid,
            m.school,
            m.layer,
            m.indicator,
            m.discipline,
            m.term,
            m.term_end,
            m.is_current_week,
            m.period_type,
            m.period_label,
            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal

        union all

        select
            m.academic_year,
            m.region,

            null as schoolid,
            'All' as school,

            m.layer,
            m.indicator,
            m.discipline,

            /* region scope spans every member school's calendar (Task 9's
            period-grain rows carry each school's own term/term_end); a
            calendar week is uniform network-wide, so min/max collapse to the
            single shared date on week rows and only widen to an envelope on
            month/quarter/ytd rows, where member schools' windows differ */
            min(m.term) as term,
            max(m.term_end) as term_end,

            m.is_current_week,
            m.period_type,
            m.period_label,

            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal,

            case
                g.aggregation_type
                when 'Average'
                then round(avg(m.metric_value), 3)
                when 'Divide'
                then round(safe_divide(sum(m.numerator), sum(m.denominator)), 3)
                when 'Sum'
                then round(sum(m.metric_value), 0)
            end as metric_aggregate_value,
        from student_metrics_all as m
        left join
            {{ ref("int_google_sheets__topline_aggregate_goals") }} as g
            on m.region = g.entity
            and m.grade_level between g.grade_low and g.grade_high
            and m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'region'
        group by
            m.academic_year,
            m.region,
            m.layer,
            m.indicator,
            m.discipline,
            m.is_current_week,
            m.period_type,
            m.period_label,
            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal

        union all

        select
            m.academic_year,

            'All' as region,
            null as schoolid,
            'All' as school,

            m.layer,
            m.indicator,
            m.discipline,

            /* org scope spans every region's school calendar (Task 9's
            period-grain rows carry each school's own term/term_end); a
            calendar week is uniform network-wide, so min/max collapse to the
            single shared date on week rows and only widen to an envelope on
            month/quarter/ytd rows, where regions' windows differ */
            min(m.term) as term,
            max(m.term_end) as term_end,

            m.is_current_week,
            m.period_type,
            m.period_label,

            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal,

            case
                g.aggregation_type
                when 'Average'
                then round(avg(m.metric_value), 3)
                when 'Divide'
                then round(safe_divide(sum(m.numerator), sum(m.denominator)), 3)
                when 'Sum'
                then round(sum(m.metric_value), 0)
            end as metric_aggregate_value,
        from student_metrics_all as m
        left join
            {{ ref("int_google_sheets__topline_aggregate_goals") }} as g
            on m.grade_level between g.grade_low and g.grade_high
            and m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'org'
        group by
            m.academic_year,
            m.layer,
            m.indicator,
            m.discipline,
            m.is_current_week,
            m.period_type,
            m.period_label,
            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal
    ),

    staff_metrics_weekly as (
        select
            *,

            'week' as period_type,

            format_date('%G-W%V', week_start_monday) as period_label,
        from {{ ref("int_topline__staff_metrics") }}
    ),

    agg_union_staff as (
        select
            m.academic_year,
            m.region,
            m.home_work_location_powerschool_school_id as schoolid,
            m.home_work_location_name as school,
            m.layer,
            m.indicator,

            cast(null as string) as discipline,

            m.term,
            m.week_end_sunday as term_end,
            m.is_current_week,
            m.period_type,
            m.period_label,

            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal,

            case
                g.aggregation_type
                when 'Average'
                then round(avg(m.metric_value), 3)
                when 'Divide'
                then round(safe_divide(sum(m.numerator), sum(m.denominator)), 3)
                when 'Sum'
                then round(sum(m.metric_value), 0)
            end as metric_aggregate_value,
        from staff_metrics_weekly as m
        left join
            {{ ref("int_google_sheets__topline_aggregate_goals") }} as g
            on m.region = g.entity
            and m.home_work_location_powerschool_school_id = g.schoolid
            and m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'school'
        group by
            m.academic_year,
            m.region,
            m.home_work_location_powerschool_school_id,
            m.home_work_location_name,
            m.layer,
            m.indicator,
            m.term,
            m.week_end_sunday,
            m.is_current_week,
            m.period_type,
            m.period_label,
            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal

        union all

        select
            m.academic_year,
            m.region,

            null as schoolid,
            'All' as school,

            m.layer,
            m.indicator,

            cast(null as string) as discipline,

            m.term,
            m.week_end_sunday as term_end,
            m.is_current_week,
            m.period_type,
            m.period_label,

            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal,

            case
                g.aggregation_type
                when 'Average'
                then round(avg(m.metric_value), 3)
                when 'Divide'
                then round(safe_divide(sum(m.numerator), sum(m.denominator)), 3)
                when 'Sum'
                then round(sum(m.metric_value), 0)
            end as metric_aggregate_value,
        from staff_metrics_weekly as m
        left join
            {{ ref("int_google_sheets__topline_aggregate_goals") }} as g
            on m.region = g.entity
            and m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'region'
        group by
            m.academic_year,
            m.region,
            m.layer,
            m.indicator,
            m.term,
            m.week_end_sunday,
            m.is_current_week,
            m.period_type,
            m.period_label,
            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal

        union all

        select
            m.academic_year,

            'All' as region,
            null as schoolid,
            'All' as school,

            m.layer,
            m.indicator,

            cast(null as string) as discipline,

            m.term,
            m.week_end_sunday as term_end,
            m.is_current_week,
            m.period_type,
            m.period_label,

            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal,

            case
                g.aggregation_type
                when 'Average'
                then round(avg(m.metric_value), 3)
                when 'Divide'
                then round(safe_divide(sum(m.numerator), sum(m.denominator)), 3)
                when 'Sum'
                then round(sum(m.metric_value), 0)
            end as metric_aggregate_value,
        from staff_metrics_weekly as m
        left join
            {{ ref("int_google_sheets__topline_aggregate_goals") }} as g
            on m.layer = g.layer
            and m.indicator = g.topline_indicator
            and g.org_level = 'org'
        group by
            m.academic_year,
            m.region,
            m.layer,
            m.indicator,
            m.term,
            m.week_end_sunday,
            m.is_current_week,
            m.period_type,
            m.period_label,
            g.indicator_display,
            g.org_level,
            g.has_goal,
            g.goal_type,
            g.goal_direction,
            g.aggregation_data_type,
            g.aggregation_type,
            g.aggregation_hash,
            g.aggregation_display,
            g.goal

        union all

        select
            academic_year,
            region,
            schoolid,

            cast(school as string) as school,

            layer,
            indicator,

            cast(null as string) as discipline,

            week_start_monday as term,
            week_end_sunday as term_end,
            is_current_week,

            'week' as period_type,

            format_date('%G-W%V', week_start_monday) as period_label,

            indicator_display,
            org_level,
            has_goal,
            goal_type,
            goal_direction,
            aggregation_data_type,
            aggregation_type,
            aggregation_hash,
            aggregation_display,
            goal,
            metric_aggregate_value,
        from {{ ref("int_topline__seats_staffed_weekly_aggregations") }}
    ),

    retention as (
        select
            academic_year,
            region,
            schoolid,
            school,
            layer,
            indicator,

            cast(null as string) as discipline,

            term,
            term_end,
            is_current_week,

            'week' as period_type,

            format_date('%G-W%V', term) as period_label,

            indicator_display,
            org_level,
            has_goal,
            goal_type,
            goal_direction,
            aggregation_data_type,
            aggregation_type,
            aggregation_hash,
            aggregation_display,
            goal,
            metric_aggregate_value,
        from {{ ref("int_topline__student_retention_weekly_aggregations") }}
    ),

    agg_week_and_period as (
        select
            'Student Metrics' as metric_type,

            academic_year,
            region,
            schoolid,
            school,
            layer,
            indicator,
            discipline,
            term,
            term_end,
            is_current_week,
            period_type,
            period_label,
            indicator_display,
            org_level,
            has_goal,
            goal_type,
            goal_direction,
            aggregation_data_type,
            aggregation_type,
            aggregation_hash,
            aggregation_display,
            goal,
            metric_aggregate_value,
        from pre_agg_union_student

        union all

        select
            'Student Metrics' as metric_type,

            academic_year,
            region,
            schoolid,
            school,
            layer,
            indicator,
            discipline,
            term,
            term_end,
            is_current_week,
            period_type,
            period_label,
            indicator_display,
            org_level,
            has_goal,
            goal_type,
            goal_direction,
            aggregation_data_type,
            aggregation_type,
            aggregation_hash,
            aggregation_display,
            goal,
            metric_aggregate_value,
        from retention

        union all

        select
            'Staff Metrics' as metric_type,

            academic_year,
            region,
            schoolid,
            school,
            layer,
            indicator,
            discipline,
            term,
            term_end,
            is_current_week,
            period_type,
            period_label,
            indicator_display,
            org_level,
            has_goal,
            goal_type,
            goal_direction,
            aggregation_data_type,
            aggregation_type,
            aggregation_hash,
            aggregation_display,
            goal,
            metric_aggregate_value,
        from agg_union_staff
    ),

    keyed as (
        select *, coalesce(cast(schoolid as string), region) as scope_key,
        from agg_week_and_period
    ),

    rollup_config as (
        /* TODO(#4363): repoint to int_google_sheets__topline_aggregate_goals
           .period_rollup at sheet cutover (plan Task 13) */
        select layer, topline_indicator, period_rollup,
        from {{ ref("seed_topline_period_rollup") }}
    ),

    flags as (
        select k.*, p.is_current_period, p.is_most_recent_complete_period,
        from keyed as k
        left join
            {{ ref("int_topline__periods") }} as p
            on k.scope_key = p.scope_key
            and k.academic_year = p.academic_year
            and k.period_type = p.period_type
            and k.period_label = p.period_label
    ),

    as_of_candidates as (
        select
            f.*,

            p.period_type as p_period_type,
            p.period_label as p_period_label,
            p.period_start as p_period_start,
            p.period_end as p_period_end,
            p.is_current_period as p_is_current_period,
            p.is_most_recent_complete_period as p_is_most_recent_complete_period,

            max(f.term) over (
                partition by
                    f.metric_type,
                    f.academic_year,
                    f.scope_key,
                    f.region,
                    f.schoolid,
                    f.school,
                    f.layer,
                    f.indicator,
                    f.discipline,
                    f.aggregation_hash,
                    p.period_type,
                    p.period_label
            ) as max_term_in_period,
        from flags as f
        inner join
            {{ ref("int_topline__periods") }} as p
            on f.scope_key = p.scope_key
            and f.academic_year = p.academic_year
            and f.term between p.period_start and p.period_end
            and p.period_type != 'week'
        left join
            rollup_config as rc
            on f.layer = rc.layer
            and f.indicator = rc.topline_indicator
        where
            f.period_type = 'week'
            and (rc.period_rollup = 'as_of' or rc.period_rollup is null)
    ),

    as_of_rows as (
        select
            * except (
                term,
                term_end,
                period_type,
                period_label,
                is_current_week,
                is_current_period,
                is_most_recent_complete_period,
                p_period_type,
                p_period_label,
                p_period_start,
                p_period_end,
                p_is_current_period,
                p_is_most_recent_complete_period,
                max_term_in_period
            ),

            /* null so the final coalesce falls through to is_current_period —
               the source week's currency flag is not this period's */
            cast(null as boolean) as is_current_week,

            p_period_start as term,
            p_period_end as term_end,
            p_period_type as period_type,
            p_period_label as period_label,
            p_is_current_period as is_current_period,
            p_is_most_recent_complete_period as is_most_recent_complete_period,
        from as_of_candidates
        where term = max_term_in_period
    ),

    all_rows as (
        select
            metric_type,
            academic_year,
            region,
            scope_key,
            schoolid,
            school,
            layer,
            indicator,
            discipline,
            term,
            term_end,
            is_current_week,
            period_type,
            period_label,
            is_current_period,
            is_most_recent_complete_period,
            indicator_display,
            org_level,
            has_goal,
            goal_type,
            goal_direction,
            aggregation_data_type,
            aggregation_type,
            aggregation_hash,
            aggregation_display,
            goal,
            metric_aggregate_value,
        from flags

        union all

        select
            metric_type,
            academic_year,
            region,
            scope_key,
            schoolid,
            school,
            layer,
            indicator,
            discipline,
            term,
            term_end,
            is_current_week,
            period_type,
            period_label,
            is_current_period,
            is_most_recent_complete_period,
            indicator_display,
            org_level,
            has_goal,
            goal_type,
            goal_direction,
            aggregation_data_type,
            aggregation_type,
            aggregation_hash,
            aggregation_display,
            goal,
            metric_aggregate_value,
        from as_of_rows
    ),

    enrollment as (
        select
            *,

            case
                when org_level = 'org'
                then org_level
                when org_level = 'region'
                then region
                when org_level = 'school'
                then cast(schoolid as string)
            end as join_key,
        from all_rows
        where indicator = 'Total Enrollment (Without SC OOD)'
    ),

    targets as (
        select e.*, t.seat_target, t.budget_target,
        from enrollment as e
        inner join
            {{ ref("stg_google_sheets__topline_enrollment_targets") }} as t
            on e.academic_year = t.academic_year
            and e.join_key = t.join_key
    ),

    target_unpivot as (
        select
            metric_type,
            academic_year,
            region,
            scope_key,
            schoolid,
            school,
            layer,
            discipline,
            term,
            term_end,
            is_current_week,
            period_type,
            period_label,
            is_current_period,
            is_most_recent_complete_period,
            indicator_display,
            org_level,
            has_goal,
            goal_type,
            goal_direction,
            aggregation_data_type,
            aggregation_type,
            aggregation_hash,
            aggregation_display,
            metric_aggregate_value,

            cast(target_value as int) as goal,

            if(
                target_type = 'seat_target', 'Seat Target', 'Budget Target'
            ) as indicator,
        from
            targets
            unpivot (target_value for target_type in (seat_target, budget_target))
    ),

    target_goals as (
        select
            tu.metric_type,
            tu.academic_year,
            tu.region,
            tu.scope_key,
            tu.schoolid,
            tu.school,
            tu.layer,
            tu.indicator,
            tu.discipline,
            tu.term,
            tu.term_end,
            tu.is_current_week,
            tu.period_type,
            tu.period_label,
            tu.is_current_period,
            tu.is_most_recent_complete_period,

            tg.indicator_display,
            tg.org_level,
            tg.has_goal,
            tg.goal_type,
            tg.goal_direction,
            tg.aggregation_data_type,
            tg.aggregation_type,
            tg.aggregation_hash,
            tg.aggregation_display,
            tg.goal,

            round(
                safe_divide(tu.metric_aggregate_value, tu.goal), 3
            ) as metric_aggregate_value,
        from target_unpivot as tu
        inner join
            {{ ref("int_google_sheets__topline_aggregate_goals") }} as tg
            on tu.indicator = tg.topline_indicator
            and tu.layer = tg.layer
            and tu.aggregation_hash = tg.aggregation_hash
            and tg.has_goal
    ),

    with_target_rows as (
        select
            metric_type,
            academic_year,
            region,
            scope_key,
            schoolid,
            school,
            layer,
            indicator,
            discipline,
            term,
            term_end,
            is_current_week,
            period_type,
            period_label,
            is_current_period,
            is_most_recent_complete_period,
            indicator_display,
            org_level,
            has_goal,
            goal_type,
            goal_direction,
            aggregation_data_type,
            aggregation_type,
            aggregation_hash,
            aggregation_display,
            goal,
            metric_aggregate_value,
        from all_rows

        union all

        select
            metric_type,
            academic_year,
            region,
            scope_key,
            schoolid,
            school,
            layer,
            indicator,
            discipline,
            term,
            term_end,
            is_current_week,
            period_type,
            period_label,
            is_current_period,
            is_most_recent_complete_period,
            indicator_display,
            org_level,
            has_goal,
            goal_type,
            goal_direction,
            aggregation_data_type,
            aggregation_type,
            aggregation_hash,
            aggregation_display,
            goal,
            metric_aggregate_value,
        from target_goals
    ),

    resolved_goals as (
        select
            r.*,

            coalesce(pg1.goal, pg2.goal, pg3.goal, pg4.goal, r.goal) as goal_resolved,
        from with_target_rows as r
        left join
            {{ ref("stg_google_sheets__topline_period_goals") }} as pg1
            on r.layer = pg1.layer
            and r.indicator = pg1.topline_indicator
            and r.aggregation_hash = pg1.aggregation_hash
            and r.period_type = pg1.period_type
            and r.period_label = pg1.period_label
            and r.academic_year = pg1.academic_year
            and r.has_goal
        left join
            {{ ref("stg_google_sheets__topline_period_goals") }} as pg2
            on r.layer = pg2.layer
            and r.indicator = pg2.topline_indicator
            and r.aggregation_hash = pg2.aggregation_hash
            and r.period_type = pg2.period_type
            and r.period_label = pg2.period_label
            and pg2.academic_year is null
            and r.has_goal
        left join
            {{ ref("stg_google_sheets__topline_period_goals") }} as pg3
            on r.layer = pg3.layer
            and r.indicator = pg3.topline_indicator
            and r.aggregation_hash = pg3.aggregation_hash
            and r.period_type = pg3.period_type
            and r.academic_year = pg3.academic_year
            and pg3.period_label is null
            and r.has_goal
        left join
            {{ ref("stg_google_sheets__topline_period_goals") }} as pg4
            on r.layer = pg4.layer
            and r.indicator = pg4.topline_indicator
            and r.aggregation_hash = pg4.aggregation_hash
            and r.period_type = pg4.period_type
            and pg4.period_label is null
            and pg4.academic_year is null
            and r.has_goal
    )

select
    metric_type,
    academic_year,
    region,
    schoolid,
    school,
    layer,
    indicator,
    discipline,
    term,
    term_end,
    period_type,
    period_label,
    is_current_period,
    is_most_recent_complete_period,
    indicator_display,
    org_level,
    has_goal,
    goal_type,
    goal_direction,
    aggregation_data_type,
    aggregation_type,
    aggregation_hash,
    aggregation_display,
    metric_aggregate_value,

    goal_resolved as goal,

    coalesce(is_current_week, is_current_period) as is_current_week,

    if(
        aggregation_data_type = 'Numeric', metric_aggregate_value, null
    ) as metric_aggregate_value_numeric,
    if(
        aggregation_data_type = 'Integer', metric_aggregate_value, null
    ) as metric_aggregate_value_integer,

    case
        when not has_goal
        then null
        when goal_direction = 'baseball' and metric_aggregate_value >= goal_resolved
        then true
        when goal_direction = 'golf' and metric_aggregate_value < goal_resolved
        then true
        else false
    end as is_goal_met,

    case
        when not has_goal
        then null
        when goal_direction = 'baseball'
        then (goal_resolved - metric_aggregate_value) / goal_resolved
        when goal_direction = 'golf'
        then (metric_aggregate_value - goal_resolved) / goal_resolved
    end as goal_difference_percent,

    if(
        case
            when not has_goal
            then null
            when goal_direction = 'baseball'
            then safe_divide(metric_aggregate_value, goal_resolved)
            when goal_direction = 'golf'
            then greatest(0, safe_divide(goal_resolved, metric_aggregate_value))
        end
        > 1,
        1,
        case
            when not has_goal
            then null
            when goal_direction = 'baseball'
            then safe_divide(metric_aggregate_value, goal_resolved)
            when goal_direction = 'golf'
            then greatest(0, safe_divide(goal_resolved, metric_aggregate_value))
        end
    ) as progress_to_goal_pct,
from resolved_goals
where term <= current_date('{{ var("local_timezone") }}')
