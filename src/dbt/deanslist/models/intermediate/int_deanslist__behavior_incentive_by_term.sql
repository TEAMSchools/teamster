with
    incentive_behaviors as (
        select
            student_school_id,
            dl_school_id,
            academic_year,
            behavior,
            behavior_date,

            case
                behavior
                when 'Earned Quarterly Incentive'
                then 'Quarters'
                when 'Earned Monthly Incentive'
                then 'Months'
                when 'Earned Weekly Incentive'
                then 'Weeks'
                when 'Progress to Quarterly Incentive'
                then 'Weeks'
            end as term_type,
        from {{ ref("stg_deanslist__behavior") }}
        where
            behavior in (
                'Earned Quarterly Incentive',
                'Earned Monthly Incentive',
                'Earned Weekly Incentive',
                'Progress to Quarterly Incentive'
            )
    ),

    terms as (
        select
            school_id,
            academic_year,
            term_type,
            term_name,
            start_date_date,
            end_date_date,

            concat('Q', right(term_name, 1)) as quarter_label,
        from {{ ref("stg_deanslist__terms") }}
    )

-- one row per student, incentive, and term: several behaviors can fall in one term
select distinct
    b.student_school_id,
    b.behavior,

    t.academic_year,
    t.start_date_date as `start_date`,
    t.end_date_date as end_date,
    t.school_id,

    if(
        b.behavior = 'Progress to Quarterly Incentive',
        concat(t.term_type, ' (Progress to Quarterly Incentive)'),
        t.term_type
    ) as incentive_type,
    if(t.term_type = 'Quarters', t.quarter_label, t.term_name) as term_name,
from incentive_behaviors as b
inner join
    terms as t
    on b.academic_year = t.academic_year
    and b.dl_school_id = t.school_id
    and b.term_type = t.term_type
    and b.behavior_date between t.start_date_date and t.end_date_date
