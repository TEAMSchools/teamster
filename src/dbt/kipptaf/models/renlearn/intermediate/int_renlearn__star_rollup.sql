select
    student_display_id,
    state_benchmark_category_level,
    state_benchmark_category_name,
    state_benchmark_proficient,
    district_benchmark_category_level,
    district_benchmark_category_name,
    district_benchmark_proficient,
    unified_score,
    screening_period_window_name,

    safe_cast(left(school_year, 4) as int) as academic_year,
    safe_cast(if(grade = 'K', '0', grade) as int) as grade_level,
    case
        when _dagster_partition_subject = 'SM'
        then 'Math'
        when _dagster_partition_subject = 'SR'
        then 'Reading'
        when _dagster_partition_subject = 'SEL'
        then 'Early Literacy'
    end as star_subject,
    case
        when _dagster_partition_subject = 'SM'
        then 'Math'
        when grade = 'K' and _dagster_partition_subject = 'SEL'
        then 'ELA'
        when _dagster_partition_subject = 'SR'
        then 'ELA'
    end as star_discipline,
    row_number() over (
        partition by
            student_display_id,
            _dagster_partition_subject,
            school_year,
            screening_period_window_name
        order by completed_date desc
    ) as rn_subj_round,
    row_number() over (
        partition by
            student_display_id,
            _dagster_partition_subject,
            school_year,
            screening_period_window_name
        order by completed_date desc
    ) as rn_subj_year,
from {{ ref("stg_renlearn__star") }}
where deactivation_reason is null
