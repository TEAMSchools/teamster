with
    star_crosswalk as (
        select 'K' as grade, subject,
        from unnest(['SM', 'SEL']) as subject
        union all
        select grade, subject,
        from unnest(['1', '2']) as grade
        cross join unnest(['SM', 'SR']) as subject
    ),

    star as (
        select
            s.student_display_id,
            safe_cast(left(s.school_year, 4) as numeric) as academic_year,
            safe_cast(if(s.grade = 'K', '0', s.grade) as numeric) as grade_level,
            if(s._dagster_partition_subject = 'SM', 'math', 'reading') as subject,
            s.district_benchmark_proficient as star_is_proficient,
            row_number() over (
                partition by
                    s.student_display_id,
                    s._dagster_partition_subject,
                    s.school_year,
                    s.screening_period_window_name
                order by s.completed_date desc
            ) as rn_subj_round,
        from {{ ref("stg_renlearn__star") }} as s
        inner join
            star_crosswalk as c
            on s.grade = c.grade
            and s._dagster_partition_subject = c.subject
        where s.screening_period_window_name = 'Winter'
    )

select
    academic_year_int as academic_year,
    concat('i-Ready ', lower(subject), ' typical growth') as domain,
    cast(if(student_grade = 'K', '0', student_grade) as numeric) as grade_level,
    round(
        avg(if(percent_progress_to_annual_typical_growth_percent >= 100, 1, 0)), 2
    ) as pct_met,
from {{ ref("base_iready__diagnostic_results") }}
where test_round = 'EOY' and rn_subj_round = 1 and region = 'KIPP Miami'
group by academic_year_int, subject, student_grade

union all

select
    academic_year_int as academic_year,
    concat('i-Ready ', lower(subject), ' stretch growth') as domain,
    safe_cast(if(student_grade = 'K', '0', student_grade) as numeric) as grade_level,
    round(
        avg(if(percent_progress_to_annual_stretch_growth_percent >= 100, 1, 0)), 2
    ) as pct_met,
from {{ ref("base_iready__diagnostic_results") }}
where test_round = 'EOY' and rn_subj_round = 1 and region = 'KIPP Miami'
group by academic_year_int, subject, student_grade

union all

select
    academic_year,
    concat('FAST ', lower(assessment_subject), ' proficiency') as domain,
    assessment_grade as grade_level,
    round(avg(if(is_proficient, 1, 0)), 2) as pct_met,
from {{ ref("stg_fldoe__fast") }}
where administration_window = 'PM3'
group by academic_year, assessment_subject, assessment_grade

union all

select
    academic_year,
    concat('STAR ', subject, ' proficiency') as domain,
    grade_level,
    round(avg(if(star_is_proficient = 'Yes', 1, 0)), 2) as pct_met
from star
where rn_subj_round = 1
group by academic_year, subject, grade_level
