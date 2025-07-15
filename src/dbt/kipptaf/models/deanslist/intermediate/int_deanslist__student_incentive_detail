with
    terms as (
        select
            term_type,
            term_name,
            school_id,

            cast(left(t.academic_year_name, 4) as int64) as academic_year,
            extract(date from t.start_date_date) as start_date,
            extract(date from t.end_date_date) as end_date,
        from {{ ref("stg_deanslist__terms") }} as t
    ),

    behaviors as (
        select
            student_school_id,
            dl_school_id,
            behavior,
            behavior_date,

            {{
                date_to_fiscal_year(
                    date_field="behavior_date", start_month=7, year_source="start"
                )
            }} as academic_year,
        from {{ ref("stg_deanslist__behavior") }}
        where behavior_category = 'Earned Incentives'
    )

select
    t.term_type as incentive_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id,

    b.student_school_id,
    max(b.behavior) as behavior,
from behaviors as b
inner join
    terms as t
    on b.academic_year = t.academic_year
    and b.dl_school_id = t.school_id
    and b.behavior_date between t.start_date and t.end_date
    and t.term_type = 'Quarters'
where b.behavior = 'Earned Quarterly Incentive'
group by
    t.term_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id,
    b.student_school_id

union all

select
    t.term_type as incentive_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id,

    b.student_school_id,
    max(b.behavior) as behavior,
from behaviors as b
inner join
    terms as t
    on b.academic_year = t.academic_year
    and b.dl_school_id = t.school_id
    and b.behavior_date between t.start_date and t.end_date
    and t.term_type = 'Months'
where b.behavior = 'Earned Monthly Incentive'
group by
    t.term_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id,
    b.student_school_id

union all

select
    t.term_type as incentive_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id,

    b.student_school_id,
    max(b.behavior) as behavior,
from behaviors as b
inner join
    terms as t
    on b.academic_year = t.academic_year
    and b.dl_school_id = t.school_id
    and b.behavior_date between t.start_date and t.end_date
    and t.term_type = 'Weeks'
where b.behavior = 'Earned Weekly Incentive'
group by
    t.term_type,
    t.academic_year,
    t.term_name,
    t.start_date,
    t.end_date,
    t.school_id,
    b.student_school_id
