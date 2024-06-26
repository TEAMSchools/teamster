with
    measures_long as (
        select
            observer_employee_number,
            academic_year,
            term_code,
            row_score as row_score_value,

            safe_cast(right(term_code, 1) as int) as term_num,

            upper(
                regexp_replace(
                    regexp_replace(measurement_name, r'[&\-]', ''), r':.*', ''
                )
            ) as score_measurement_shortname,
        from {{ ref("int_performance_management__observation_details") }}
        where
            rubric_name = 'Coaching Tool: Coach ETR and Reflection'
            and row_score is not null
    ),

    pivots as (
        select
            observer_employee_number,
            academic_year,
            term_code,
            term_num,
            etr1a,
            etr1b,
            etr2a,
            etr2b,
            etr2c,
            etr2d,
            etr3a,
            etr3b,
            etr3c,
            etr3d,
            etr4a,
            etr4b,
            etr4c,
            etr4d,
            etr4e,
            etr4f,
            etr5a,
            etr5b,
            etr5c,
            so01,
            so02,
            so03,
            so04,
            so05,
            so06,
            so07,
            so08,
        from
            measures_long pivot (
                avg(row_score_value)
                for score_measurement_shortname in (
                    'ETR1A',
                    'ETR1B',
                    'ETR2A',
                    'ETR2B',
                    'ETR2C',
                    'ETR2D',
                    'ETR3A',
                    'ETR3B',
                    'ETR3C',
                    'ETR3D',
                    'ETR4A',
                    'ETR4B',
                    'ETR4C',
                    'ETR4D',
                    'ETR4E',
                    'ETR4F',
                    'ETR5A',
                    'ETR5B',
                    'ETR5C',
                    'SO01',
                    'SO02',
                    'SO03',
                    'SO04',
                    'SO05',
                    'SO06',
                    'SO07',
                    'SO08'
                )
            )
    ),

    manager_overall as (
        select
            observer_employee_number,
            academic_year,
            term_code,
            avg(observation_score) as overall_score,
        from {{ ref("int_performance_management__observation_details") }}
        where rubric_name = 'Coaching Tool: Coach ETR and Reflection'
        group by observer_employee_number, academic_year, term_code
    )

select
    p.observer_employee_number,
    p.academic_year,
    p.term_code as form_term,
    p.term_num,
    p.etr1a,
    p.etr1b,
    p.etr2a,
    p.etr2b,
    p.etr2c,
    p.etr2d,
    p.etr3a,
    p.etr3b,
    p.etr3c,
    p.etr3d,
    p.etr4a,
    p.etr4b,
    p.etr4c,
    p.etr4d,
    p.etr4e,
    p.etr4f,
    p.etr5a,
    p.etr5b,
    p.etr5c,
    p.so01 as so1,
    p.so02 as so2,
    p.so03 as so3,
    p.so04 as so4,
    p.so05 as so5,
    p.so06 as so6,
    p.so07 as so7,
    p.so08 as so8,

    m.overall_score,
from pivots as p
inner join
    manager_overall as m
    on p.observer_employee_number = m.observer_employee_number
    and p.academic_year = m.academic_year
    and p.term_code = m.term_code
