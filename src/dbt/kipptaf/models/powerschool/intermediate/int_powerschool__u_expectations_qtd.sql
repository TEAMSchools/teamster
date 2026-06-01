with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    term_weeks as (
        /*
        grain projection: every selected column is functionally determined
        by the partition key; not a mask for upstream duplicates
        */
        select distinct
            _dbt_source_relation,
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
                partition_by="_dbt_source_relation, region, school_level, `quarter`",
                order_by="week_number_quarter desc",
            )
        }}
    )

select
    u.school_level,
    u.`quarter`,
    u.cnt_w,
    u.cnt_h,
    u.cnt_f,
    u.cnt_s,

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
    and {{ union_dataset_join_clause(left_alias="u", right_alias="cw") }}
