with
    metrics as (
        select
            student_number,
            academic_year,
            term_name,
            region,
            grade_level,
            ada_term_running,
            n_absences_y1_running,
            n_absences_y1_running_non_susp,
            n_absences_y1_running_non_susp_no_tardy,
            projected_credits_y1_term,
            projected_credits_cum,

            cast(iready_reading_levels_below as float64) as iready_reading_levels_below,
            cast(iready_math_levels_below as float64) as iready_math_levels_below,
            cast(dibels_composite_level as float64) as dibels_composite_level,
            cast(star_ela_level as float64) as star_ela_level,
            cast(star_math_level as float64) as star_math_level,
            cast(fast_ela_level as float64) as fast_ela_level,
            cast(fast_math_level as float64) as fast_math_level,
            cast(n_failing as float64) as n_failing,
            cast(n_failing_core as float64) as n_failing_core,
        from {{ ref("int_students__promotional_status_metrics") }}
    )

select
    student_number, academic_year, term_name, region, grade_level, metric, metric_value,
from
    metrics unpivot include nulls(
        metric_value for metric in (
            ada_term_running,
            n_absences_y1_running,
            n_absences_y1_running_non_susp,
            n_absences_y1_running_non_susp_no_tardy,
            iready_reading_levels_below,
            iready_math_levels_below,
            dibels_composite_level,
            star_ela_level,
            star_math_level,
            fast_ela_level,
            fast_math_level,
            n_failing,
            n_failing_core,
            projected_credits_y1_term,
            projected_credits_cum
        )
    )
