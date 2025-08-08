select
    b.student_school_id,

    t.term_type as incentive_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id,

    max(b.behavior) as behavior,
from {{ ref("stg_deanslist__behavior") }} as b
inner join
    {{ ref("stg_deanslist__terms") }} as t
    on b.academic_year = t.academic_year
    and b.dl_school_id = t.school_id
    and b.behavior_date between t.start_date_date and t.end_date_date
    and t.term_type = 'Quarters'
where b.behavior = 'Earned Quarterly Incentive'
group by
    b.student_school_id,
    t.term_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id

union all

select
    b.student_school_id,

    t.term_type as incentive_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id,

    max(b.behavior) as behavior,
from {{ ref("stg_deanslist__behavior") }} as b
inner join
    {{ ref("stg_deanslist__terms") }} as t
    on b.academic_year = t.academic_year
    and b.dl_school_id = t.school_id
    and b.behavior_date between t.start_date_date and t.end_date_date
    and t.term_type = 'Months'
where b.behavior = 'Earned Monthly Incentive'
group by
    b.student_school_id,
    t.term_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id

union all

select
    b.student_school_id,

    t.term_type as incentive_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id,

    max(b.behavior) as behavior,
from {{ ref("stg_deanslist__behavior") }} as b
inner join
    {{ ref("stg_deanslist__terms") }} as t
    on b.academic_year = t.academic_year
    and b.dl_school_id = t.school_id
    and b.behavior_date between t.start_date_date and t.end_date_date
    and t.term_type = 'Weeks'
where b.behavior = 'Earned Weekly Incentive'
group by
    b.student_school_id,
    t.term_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id
