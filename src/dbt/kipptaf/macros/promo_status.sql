{% macro promo_status_metric_columns() %}
    {{
        return(
            [
                "ada_term_running",
                "n_absences_y1_running",
                "n_absences_y1_running_non_susp",
                "n_absences_y1_running_non_susp_no_tardy",
                "iready_reading_levels_below",
                "iready_math_levels_below",
                "dibels_composite_level",
                "star_ela_level",
                "star_math_level",
                "fast_ela_level",
                "fast_math_level",
                "n_failing",
                "n_failing_core",
                "projected_credits_y1_term",
                "projected_credits_cum",
            ]
        )
    }}
{% endmacro %}

{% macro promo_status_pseudo_metric_columns() %}
    {{ return(["is_off_track_attendance", "is_off_track_academic"]) }}
{% endmacro %}
