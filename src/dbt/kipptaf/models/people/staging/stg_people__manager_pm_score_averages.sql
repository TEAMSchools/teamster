with measures_long AS (
SELECT observer_employee_number,
       academic_year,
       form_term,
       CASE
        WHEN measurement_name = 'This teammate addresses challenges directly and productively.' THEN 'SO1'
        WHEN measurement_name = 'This teammate chooses to make work a positive and joyful experience for students, self, and others.' THEN 'SO2'
        WHEN measurement_name = 'This teammate demonstrates professional responsibilities and individual commitments.' THEN 'SO3'
        WHEN measurement_name = 'This teammate makes others feel included, loved, and valued, even across cultural differences.' THEN 'SO4'
        WHEN measurement_name = 'This teammate meets professional expectations for presence.' THEN 'SO5'
        WHEN measurement_name = 'This teammate meets professional expectations for punctuality.' THEN 'SO6'
        WHEN measurement_name = 'This teammate seeks feedback and takes it seriously.' THEN 'SO7'
        WHEN measurement_name = 'This teammate supports the collective work of the team and meets team commitments.' THEN 'SO8'
        ELSE concat('ETR',left(measurement_name,2)) 
      END as measurement_code,
       row_score_value
FROM {{ ref('rpt_tableau__schoolmint_grow_observation_details') }}
where form_long_name = 'Coaching Tool: Coach ETR and Reflection'
)

pivots AS (
SELECT p.observer_employee_number,
       p.academic_year,
       p.form_term,
       cast(right(p.form_term,1) as int64) as term_num,
       p.ETR1A,
       p.ETR1B,
       p.ETR2A,
       p.ETR2B,
       p.ETR2C,
       p.ETR2D,
       p.ETR3A,
       p.ETR3B,
       p.ETR3C,
       p.ETR3D,
       p.ETR4A,
       p.ETR4B,
       p.ETR4C,
       p.ETR4D,
       p.ETR4E,
       p.ETR4F,
       p.ETR5A,
       p.ETR5B,
       p.ETR5C,
       p.SO1,
       p.SO2,
       p.SO3,
       p.SO4,
       p.SO5,
       p.SO6,
       p.SO7,
       p.SO8,
FROM measures_long
  PIVOT(
    avg(row_score_value)
    for measurement_code in ('ETR1A',
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
  ) as p
)

,manager_overall as (
  SELECT observer_employee_number,
         academic_year,
         form_term,
         avg(overall_score) as overall_score
  FROM {{ ref('rpt_tableau__schoolmint_grow_observation_details') }}
where form_long_name = 'Coaching Tool: Coach ETR and Reflection'
GROUP BY observer_employee_number, academic_year, form_term
 )

SELECT p.observer_employee_number,
       p.academic_year,
       p.form_term,
       p.term_num,
       p.ETR1A,
       p.ETR1B,
       p.ETR2A,
       p.ETR2B,
       p.ETR2C,
       p.ETR2D,
       p.ETR3A,
       p.ETR3B,
       p.ETR3C,
       p.ETR3D,
       p.ETR4A,
       p.ETR4B,
       p.ETR4C,
       p.ETR4D,
       p.ETR4E,
       p.ETR4F,
       p.ETR5A,
       p.ETR5B,
       p.ETR5C,
       p.SO1,
       p.SO2,
       p.SO3,
       p.SO4,
       p.SO5,
       p.SO6,
       p.SO7,
       p.SO8,

       m.overall_score
FROM pivots as p
inner join manager_overall as m 
  on p.observer_employee_number = m.observer_employee_number
 and p.academic_year = m.academic_year
 and p.form_term = m.form_term
