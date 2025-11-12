with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnj_renlearn", "stg_renlearn__star"),
                    source("kippmiami_renlearn", "stg_renlearn__star"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    *,

    _dagster_partition_fiscal_year - 1 as academic_year,

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

    case
        _dagster_partition_subject
        when 'SR'
        then 'Reading'
        when 'SM'
        then 'Math'
        when 'SEL'
        then 'Reading'
    end as `subject`,

    case
        screening_period_window_name
        when 'Fall'
        then 'BOY'
        when 'Winter'
        then 'MOY'
        when 'Spring'
        then 'EOY'
    end as administration_window,

    case
        when district_benchmark_proficient = 'Yes'
        then 1
        when district_benchmark_proficient = 'No'
        then 0
    end as is_district_benchmark_proficient_int,

    case
        when state_benchmark_proficient = 'Yes'
        then 1
        when state_benchmark_proficient = 'No'
        then 0
    end as is_state_benchmark_proficient_int,

    row_number() over (
        partition by
            _dbt_source_relation,
            _dagster_partition_subject,
            _dagster_partition_fiscal_year,
            student_identifier,
            screening_period_window_name
        order by completed_date desc
    ) as rn_subject_round,
from union_relations
where deactivation_reason is null
