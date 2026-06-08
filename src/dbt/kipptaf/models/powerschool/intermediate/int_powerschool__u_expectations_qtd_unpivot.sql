with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    term_weeks as (
        /*
        grain projection: every selected column is functionally determined
        by the partition key; not a mask for upstream duplicates
        */
        select distinct
            _dbt_source_project,
            region,
            school_level,
            `quarter`,
            week_number_quarter,
            week_start_monday,
            week_end_sunday,

        from {{ ref("int_powerschool__calendar_week") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and week_start_monday <= current_date('{{ var("local_timezone") }}')
    ),

    current_week as (
        {{
            dbt_utils.deduplicate(
                relation="term_weeks",
                partition_by="_dbt_source_project, region, school_level, `quarter`",
                order_by="week_number_quarter desc",
            )
        }}
    ),

    quarter_weeks as (
        select
            u.school_level,
            u.`quarter`,
            u.cnt_w,
            u.cnt_h,
            u.cnt_f,
            u.cnt_s,
            u.notes,

            cw.region,
            cw.week_number_quarter as week_number_qtd,
            cw.week_start_monday,
            cw.week_end_sunday,

        from {{ ref("stg_powerschool__u_expectations") }} as u
        inner join
            current_week as cw
            on u.school_level = cw.school_level
            and u.`quarter` = cw.`quarter`
            and u.week_number = cw.week_number_quarter
            and u._dbt_source_project = cw._dbt_source_project
    )

select
    region,
    school_level,
    `quarter`,
    week_number_qtd,
    week_start_monday,
    week_end_sunday,
    notes,

    assignment_category_code,
    expectation,

    {{ var("current_academic_year") }} as academic_year,

    concat(assignment_category_code, right(`quarter`, 1)) as assignment_category_term,

    case
        assignment_category_code
        when 'W'
        then 'Work Habits'
        when 'H'
        then 'Homework'
        when 'F'
        then 'Formative Mastery'
        when 'S'
        then 'Summative Mastery'
    end as assignment_category_name,

from
    quarter_weeks unpivot (
        expectation for assignment_category_code
        in (`cnt_w` as 'W', `cnt_h` as 'H', `cnt_f` as 'F', `cnt_s` as 'S')
    )
where expectation is not null
