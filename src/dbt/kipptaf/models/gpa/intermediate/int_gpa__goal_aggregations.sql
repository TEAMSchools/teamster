with
    student_metrics as (
        select
            academic_year,
            region,
            schoolid,
            grade_level,
            student_number,
            y1_gpa_weighted,
            y1_gpa_unweighted,
            cumulative_gpa_unweighted,
            is_on_pace,
            is_on_pace_denominator,
        from {{ ref("int_gpa__goal_student_metrics") }}
    ),

    goals as (
        select
            academic_year,
            org_level,
            region,
            schoolid,
            grade_low,
            grade_high,
            metric,
            threshold,
            direction,
            grade_band,
            aggregation_hash,
            goal_proportion,
            higher_is_better,
        from {{ ref("int_google_sheets__gpa_goals") }}
    ),

    joined_school as (
        select
            m.academic_year,
            m.region,
            m.schoolid,
            m.student_number,
            m.is_on_pace,
            m.is_on_pace_denominator,

            g.org_level,
            g.grade_band,
            g.aggregation_hash,
            g.metric,
            g.threshold,
            g.direction,
            g.goal_proportion,
            g.higher_is_better,

            case
                g.metric
                when 'y1_gpa_weighted'
                then m.y1_gpa_weighted
                when 'y1_gpa_unweighted'
                then m.y1_gpa_unweighted
                when 'cumulative_gpa_unweighted'
                then m.cumulative_gpa_unweighted
            end as measure_value,
        from student_metrics as m
        inner join
            goals as g
            on m.academic_year = g.academic_year
            and m.grade_level between g.grade_low and g.grade_high
            and m.region = g.region
            and m.schoolid = g.schoolid
            and g.org_level = 'school'
    ),

    joined_region as (
        select
            m.academic_year,
            m.region,

            cast(null as int64) as schoolid,

            m.student_number,
            m.is_on_pace,
            m.is_on_pace_denominator,

            g.org_level,
            g.grade_band,
            g.aggregation_hash,
            g.metric,
            g.threshold,
            g.direction,
            g.goal_proportion,
            g.higher_is_better,

            case
                g.metric
                when 'y1_gpa_weighted'
                then m.y1_gpa_weighted
                when 'y1_gpa_unweighted'
                then m.y1_gpa_unweighted
                when 'cumulative_gpa_unweighted'
                then m.cumulative_gpa_unweighted
            end as measure_value,
        from student_metrics as m
        inner join
            goals as g
            on m.academic_year = g.academic_year
            and m.grade_level between g.grade_low and g.grade_high
            and m.region = g.region
            and g.org_level = 'region'
    ),

    joined_org as (
        select
            m.academic_year,

            cast(null as string) as region,
            cast(null as int64) as schoolid,

            m.student_number,
            m.is_on_pace,
            m.is_on_pace_denominator,

            g.org_level,
            g.grade_band,
            g.aggregation_hash,
            g.metric,
            g.threshold,
            g.direction,
            g.goal_proportion,
            g.higher_is_better,

            case
                g.metric
                when 'y1_gpa_weighted'
                then m.y1_gpa_weighted
                when 'y1_gpa_unweighted'
                then m.y1_gpa_unweighted
                when 'cumulative_gpa_unweighted'
                then m.cumulative_gpa_unweighted
            end as measure_value,
        from student_metrics as m
        inner join
            goals as g
            on m.academic_year = g.academic_year
            and m.grade_level between g.grade_low and g.grade_high
            and g.org_level = 'org'
    ),

    agg_school as (
        select
            academic_year,
            region,
            schoolid,
            org_level,
            grade_band,
            aggregation_hash,
            metric,
            goal_proportion,
            higher_is_better,

            count(student_number) as n_students_in_grain,

            countif(
                case
                    when metric = 'on_pace'
                    then is_on_pace_denominator
                    else measure_value is not null
                end
            ) as n_students_measured,

            countif(
                case
                    when metric = 'on_pace'
                    then is_on_pace and is_on_pace_denominator
                    else
                        (direction = '>=' and measure_value >= threshold)
                        or (direction = '<=' and measure_value <= threshold)
                end
            ) as n_students_met,
        from joined_school
        group by
            academic_year,
            region,
            schoolid,
            org_level,
            grade_band,
            aggregation_hash,
            metric,
            goal_proportion,
            higher_is_better
    ),

    agg_region as (
        select
            academic_year,
            region,
            schoolid,
            org_level,
            grade_band,
            aggregation_hash,
            metric,
            goal_proportion,
            higher_is_better,

            count(student_number) as n_students_in_grain,

            countif(
                case
                    when metric = 'on_pace'
                    then is_on_pace_denominator
                    else measure_value is not null
                end
            ) as n_students_measured,

            countif(
                case
                    when metric = 'on_pace'
                    then is_on_pace and is_on_pace_denominator
                    else
                        (direction = '>=' and measure_value >= threshold)
                        or (direction = '<=' and measure_value <= threshold)
                end
            ) as n_students_met,
        from joined_region
        group by
            academic_year,
            region,
            schoolid,
            org_level,
            grade_band,
            aggregation_hash,
            metric,
            goal_proportion,
            higher_is_better
    ),

    agg_org as (
        select
            academic_year,
            region,
            schoolid,
            org_level,
            grade_band,
            aggregation_hash,
            metric,
            goal_proportion,
            higher_is_better,

            count(student_number) as n_students_in_grain,

            countif(
                case
                    when metric = 'on_pace'
                    then is_on_pace_denominator
                    else measure_value is not null
                end
            ) as n_students_measured,

            countif(
                case
                    when metric = 'on_pace'
                    then is_on_pace and is_on_pace_denominator
                    else
                        (direction = '>=' and measure_value >= threshold)
                        or (direction = '<=' and measure_value <= threshold)
                end
            ) as n_students_met,
        from joined_org
        group by
            academic_year,
            region,
            schoolid,
            org_level,
            grade_band,
            aggregation_hash,
            metric,
            goal_proportion,
            higher_is_better
    ),

    agg_union as (
        select
            academic_year,
            region,
            schoolid,
            org_level,
            grade_band,
            aggregation_hash,
            metric,
            goal_proportion,
            higher_is_better,
            n_students_in_grain,
            n_students_measured,
            n_students_met,
        from agg_school

        union all

        select
            academic_year,
            region,
            schoolid,
            org_level,
            grade_band,
            aggregation_hash,
            metric,
            goal_proportion,
            higher_is_better,
            n_students_in_grain,
            n_students_measured,
            n_students_met,
        from agg_region

        union all

        select
            academic_year,
            region,
            schoolid,
            org_level,
            grade_band,
            aggregation_hash,
            metric,
            goal_proportion,
            higher_is_better,
            n_students_in_grain,
            n_students_measured,
            n_students_met,
        from agg_org
    ),

    rates as (
        select
            academic_year,
            metric,
            aggregation_hash,
            org_level,
            region,
            schoolid,
            grade_band,
            goal_proportion,
            higher_is_better,
            n_students_in_grain,
            n_students_measured,
            n_students_met,

            /* denominator is students with a measurable value, not every student
               in the grain — an unmeasured student is not a non-achiever. Yields
               null (not 0) when nothing is measured yet, e.g. before a year's
               grades post. */
            round(safe_divide(n_students_met, n_students_measured), 3) as metric_rate,
        from agg_union
    ),

    progress as (
        select
            academic_year,
            metric,
            aggregation_hash,
            org_level,
            region,
            schoolid,
            grade_band,
            goal_proportion,
            n_students_in_grain,
            n_students_measured,
            n_students_met,
            metric_rate,

            if(
                higher_is_better,
                metric_rate >= goal_proportion,
                metric_rate <= goal_proportion
            ) as is_goal_met,

            if(
                higher_is_better,
                safe_divide(metric_rate, goal_proportion),
                safe_divide(goal_proportion, metric_rate)
            ) as progress_to_goal_raw,
        from rates
    )

select
    academic_year,
    metric,
    aggregation_hash,
    org_level,
    region,
    schoolid,
    grade_band,
    goal_proportion,
    n_students_in_grain,
    n_students_measured,
    n_students_met,
    metric_rate,
    is_goal_met,

    round(least(1.0, progress_to_goal_raw), 3) as progress_to_goal,
from progress
