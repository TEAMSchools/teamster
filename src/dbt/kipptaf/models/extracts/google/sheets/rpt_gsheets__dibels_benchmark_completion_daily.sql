with
    in_session_days as (
        select
            schoolid,
            _dbt_source_project,
            date_value,

            lead(date_value) over (
                partition by schoolid, _dbt_source_project order by date_value
            ) as next_in_session_date,

        from {{ ref("stg_powerschool__calendar_day") }}
        where insession = 1
    ),

    -- coalesce advisory once here, so the join below compares plain columns and
    -- students with no advisory are bucketed rather than lost to a null join
    students as (
        select
            academic_year,
            region,
            school,
            schoolid,
            grade_level,
            student_number,
            admin_season,
            start_date,
            end_date,
            student_status,
            test_date,
            _dbt_source_project,

            coalesce(advisory, 'Unassigned') as advisory,

        from {{ ref("int_amplify__benchmark_completion") }}
        where not is_self_contained and not is_out_of_district
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    school_windows as (
        select distinct
            academic_year,
            region,
            school,
            schoolid,
            grade_level,
            advisory,
            admin_season,
            start_date,
            end_date,
            _dbt_source_project,

        from students
    ),

    data_freshness as (
        select academic_year, region, admin_season, max(test_date) as data_through_date,

        from students
        group by academic_year, region, admin_season
    ),

    window_days as (
        select
            sw.academic_year,
            sw.region,
            sw.school,
            sw.schoolid,
            sw.grade_level,
            sw.advisory,
            sw.admin_season,
            sw.start_date as window_start_date,
            sw.end_date as window_end_date,

            isd.date_value as as_of_date,
            isd.next_in_session_date as reported_morning_of,

        from school_windows as sw
        inner join
            in_session_days as isd
            on sw.schoolid = isd.schoolid
            and sw._dbt_source_project = isd._dbt_source_project
            and isd.date_value between sw.start_date and sw.end_date
        where
            isd.date_value
            <= date_sub(current_date('{{ var("local_timezone") }}'), interval 1 day)
    ),

    student_days as (
        select
            wd.academic_year,
            wd.region,
            wd.school,
            wd.schoolid,
            wd.grade_level,
            wd.advisory,
            wd.admin_season,
            wd.window_start_date,
            wd.window_end_date,
            wd.as_of_date,
            wd.reported_morning_of,

            bc.student_number,

            case
                when bc.student_status = 'Completed' and bc.test_date <= wd.as_of_date
                then 'Completed'
                when bc.test_date <= wd.as_of_date
                then 'In Progress'
                else 'Not Started'
            end as status_as_of_date,

        from window_days as wd
        inner join
            students as bc
            on wd.academic_year = bc.academic_year
            and wd.region = bc.region
            and wd.schoolid = bc.schoolid
            and wd.grade_level = bc.grade_level
            and wd.advisory = bc.advisory
            and wd.admin_season = bc.admin_season
    ),

    daily_counts as (
        select
            academic_year,
            region,
            school,
            schoolid,
            grade_level,
            advisory,
            admin_season,
            window_start_date,
            window_end_date,
            as_of_date,
            reported_morning_of,

            count(*) as students_expected,
            countif(status_as_of_date = 'Completed') as students_completed,
            countif(status_as_of_date = 'In Progress') as students_in_progress,
            countif(status_as_of_date = 'Not Started') as students_not_started,

        from student_days
        group by
            academic_year,
            region,
            school,
            schoolid,
            grade_level,
            advisory,
            admin_season,
            window_start_date,
            window_end_date,
            as_of_date,
            reported_morning_of
    )

select
    dc.academic_year,
    dc.region,
    dc.school,
    dc.schoolid,
    dc.grade_level,
    dc.advisory,
    dc.admin_season,
    dc.window_start_date,
    dc.window_end_date,
    dc.as_of_date,
    dc.reported_morning_of,
    dc.students_expected,
    dc.students_completed,
    dc.students_in_progress,
    dc.students_not_started,

    df.data_through_date,

    round(
        safe_divide(dc.students_completed, dc.students_expected), 2
    ) as completion_rate,

from daily_counts as dc
left join
    data_freshness as df
    on dc.academic_year = df.academic_year
    and dc.region = df.region
    and dc.admin_season = df.admin_season
