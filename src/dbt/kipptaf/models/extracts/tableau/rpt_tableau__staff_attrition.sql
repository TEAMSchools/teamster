with
    terminations as (
        select
            employee_number,
            position_id,
            status_effective_date,
            status_effective_end_date,
            termination_reason_description,
            lag(status_effective_end_date) over (
                partition by position_id order by status_effective_date
            ) as prev_end_date,
        from people.status_history_static
        where position_status = 'Terminated'
    )

    /* final termination record */
    final_termination as (
        select
            *,
            row_number() over (
                partition by position_id order by status_effective_date desc
            ) as rn,
        from terminations
        where ifnull(date_diff(day, prev_end_date, status_effective_date), 2) > 1
    ),

    roster_terminations as (
        select
            r.employee_number,
            r.position_id,
            r.preferred_first_name,
            r.preferred_last_name,
            r.race_ethnicity_reporting,
            r.gender_reporting,
            r.original_hire_date,
            r.rehire_date,
            r.kipp_alumni_status,
            ifnull(r.rehire_date, r.original_hire_date) as position_start_date,

            if(
                r.position_status = 'Terminated',
                ifnull(t.status_effective_date, r.termination_date),
                null
            ) as termination_date,

            ifnull(
                t.termination_reason_description, r.termination_reason
            ) as status_reason,
        from people.staff_roster as r
        left join final_termination as t on r.position_id = t.position_id and t.rn = 1
    ),

    roster as (
        select
            *,
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="position_start_date",
                    start_month=9,
                    year_source="start",
                )
            }} as start_academic_year,
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="termination_date",
                    start_month=9,
                    year_source="start",
                )
            }} as end_academic_year,
        from roster_terminations
    ),

    years as (
        select
            n as academic_year,
            n + 1 as next_academic_year,

            date(n, 7, 1) as default_entry_date,
            date((n + 1), 6, 30) as default_exit_date,

            date(n, 9, 1) as denominator_start_date
            date((n + 1), 8, 31) as attrition_date,

            date((n + 1), 4, 30) as effective_date,
        from {{ ref("utils__date_spine") }}
        where n between 2002 and ({{ var("current_academic_year") }} + 1)
    ),

    roster_year_scaffold as (
        select
            r.*,

            y.*,

            if(
                r.end_academic_year = y.academic_year, r.termination_date, null
            ) as termination_date,

            if(
                r.start_academic_year = y.academic_year,
                r.position_start_date,
                y.default_entry_date
            ) as academic_year_entrydate,

            ifnull(
                if(r.end_academic_year = y.academic_year, r.termination_date, null),
                default_exit_date
            ) as academic_year_exitdate,
        from roster as r
        inner join
            years as y
            on y.academic_year between r.start_academic_year and r.end_academic_year
    ),

    scaffold as (
        select
            rys.*,

            w.business_unit,
            w.job_title,
            w.location,
            w.home_department,

            scw.school_level,
            scw.reporting_school_id,

            lead(rys.academic_year_exitdate, 1) over (
                partition by rys.position_id order by rys.academic_year
            ) as academic_year_exitdate_next,
        from roster_year_scaffold as rys
        left join
            people.employment_history_static as w
            on rys.position_id = w.position_id
            and rys.effective_date
            between w.effective_start_date and w.effective_end_date
        left join
            people.school_crosswalk as scw
            on w.location = scw.site_name
            and scw._fivetran_deleted = 0
        where rys.academic_year_exitdate > rys.academic_year_entrydate
    ),

    with_dates as (
        select
            *
            ifnull(rehire_date, original_hire_date) as most_recent_hire_date,
            ifnull(academic_year_exitdate_next, termination_date) as attrition_exitdate,
        from scaffold
    )

select
    employee_number as df_employee_number,
    preferred_first_name,
    preferred_last_name,
    race_ethnicity_reporting as primary_ethnicity,
    gender_reporting,
    academic_year,
    academic_year_entrydate,
    academic_year_exitdate,
    original_hire_date,
    rehire_date,
    termination_date,
    status_reason,
    job_title as primary_job,
    home_department as primary_on_site_department,
    `location` as primary_site,
    business_unit as legal_entity_name,
    reporting_school_id as primary_site_reporting_schoolid,
    school_level as primary_site_school_level,
    kipp_alumni_status,
    academic_year_exitdate_next as next_academic_year_exitdate,
    case
        when date_diff(day, academic_year_entrydate, academic_year_exitdate) <= 0
        then 0
        when
            academic_year_exitdate >= denominator_start_date
            and academic_year_entrydate <= effective_date
        then 1
        else 0
    end as is_denominator,

    if(attrition_exitdate <= attrition_date, 1, 0) as is_attrition,

    if(
        most_recent_hire_date > attrition_exitdate,
        round(datediff(day, original_hire_date, attrition_exitdate) / 365, 0),
        round(datediff(day, most_recent_hire_date, attrition_exitdate) / 365, 0)
    ) as years_at_kipp,
from attrition_exitdate
