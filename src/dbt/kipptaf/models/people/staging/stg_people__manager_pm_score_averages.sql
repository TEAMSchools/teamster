with
    measures_long as (
        select
            observer_employee_number,
            academic_year,
            form_term,
            row_score_value,
            case
                when
                    measurement_name
                    = 'This teammate addresses challenges directly and productively.'
                then 'SO1'
                when
                    measurement_name
                    = 'This teammate chooses to make work a positive and joyful experience for students, self, and others.'
                then 'SO2'
                when
                    measurement_name
                    = 'This teammate demonstrates professional responsibilities and individual commitments.'
                then 'SO3'
                when
                    measurement_name
                    = 'This teammate makes others feel included, loved, and valued, even across cultural differences.'
                then 'SO4'
                when
                    measurement_name
                    = 'This teammate meets professional expectations for presence.'
                then 'SO5'
                when
                    measurement_name
                    = 'This teammate meets professional expectations for punctuality.'
                then 'SO6'
                when
                    measurement_name
                    = 'This teammate seeks feedback and takes it seriously.'
                then 'SO7'
                when
                    measurement_name
                    = 'This teammate supports the collective work of the team and meets team commitments.'
                then 'SO8'
                else concat('ETR', left(measurement_name, 2))
            end as measurement_code,
        from {{ ref("rpt_tableau__schoolmint_grow_observation_details") }}
        where form_long_name = 'Coaching Tool: Coach ETR and Reflection'
    ),

    pivots as (
        select
            observer_employee_number,
            academic_year,
            form_term,
            cast(right(form_term, 1) as int64) as term_num,
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
            so1,
            so2,
            so3,
            so4,
            so5,
            so6,
            so7,
            so8,
        from
            measures_long pivot (
                avg(row_score_value)
                for measurement_code in (
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
                    'SO1',
                    'SO2',
                    'SO3',
                    'SO4',
                    'SO5',
                    'SO6',
                    'SO7',
                    'SO8'
                )
            )
    ),
    
    manager_overall as (
        select
            observer_employee_number,
            academic_year,
            form_term,
            avg(overall_score) as overall_score
        from {{ ref("rpt_tableau__schoolmint_grow_observation_details") }}
        where form_long_name = 'Coaching Tool: Coach ETR and Reflection'
        group by observer_employee_number, academic_year, form_term
    )

select
    p.observer_employee_number,
    p.academic_year,
    p.form_term,
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
    p.so1,
    p.so2,
    p.so3,
    p.so4,
    p.so5,
    p.so6,
    p.so7,
    p.so8,

    m.overall_score,
from pivots as p
inner join
    manager_overall as m
    on p.observer_employee_number = m.observer_employee_number
    and p.academic_year = m.academic_year
    and p.form_term = m.form_term
