with
    term as (
        select
            sub.employee_number,
            sub.position_id,
            sub.status_effective_date,
            sub.termination_reason_description,
            row_number() over (
                partition by sub.position_id order by sub.status_effective_date desc
            ) as rn
        from
            (
                select
                    employee_number,
                    position_id,
                    status_effective_date,
                    status_effective_end_date,
                    termination_reason_description,
                    lag(status_effective_end_date) over (
                        partition by position_id order by status_effective_date
                    ) as prev_end_date
                from people.status_history_static
                where position_status = 'Terminated'
            ) as sub
        where
            isnull (datediff(day, sub.prev_end_date, sub.status_effective_date), 2) > 1
    ),
    
    roster as (
        select
            sub.employee_number,
            sub.position_id,
            sub.preferred_first_name,
            sub.preferred_last_name,
            sub.race_ethnicity_reporting,
            sub.gender_reporting,
            sub.original_hire_date,
            sub.rehire_date,
            sub.position_start_date,
            sub.termination_date,
            sub.status_reason,
            sub.kipp_alumni_status,
            case
                when month(sub.position_start_date) >= 9
                then year(sub.position_start_date)
                when month(sub.position_start_date) < 9
                then year(sub.position_start_date) - 1
            end as start_academic_year,
            coalesce(
                case
                    when month(sub.termination_date) >= 9
                    then year(sub.termination_date)
                    when month(sub.termination_date) < 9
                    then year(sub.termination_date) - 1
                end,
                utilities.global_academic_year() + 1
            ) as end_academic_year
        from
            (
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
                    coalesce(
                        r.rehire_date, r.original_hire_date
                    ) as position_start_date,
                    case
                        when r.position_status != 'Terminated'
                        then null
                        else coalesce(t.status_effective_date, r.termination_date)
                    end as termination_date,
                    coalesce(
                        t.termination_reason_description, r.termination_reason
                    ) as status_reason
                from people.staff_roster as r
                /* final termination record */
                left join term as t on (r.position_id = t.position_id and t.rn = 1)
            ) as sub
    ),
    years as (
        select n as academic_year, datefromparts((n + 1), 4, 30) as effective_date
        from utilities.row_generator_smallint
        where n between 2002 and (utilities.global_academic_year() + 1)
    ),
    scaffold as (
        select
            sub.employee_number,
            sub.position_id,
            sub.preferred_first_name,
            sub.preferred_last_name,
            sub.race_ethnicity_reporting,
            sub.gender_reporting,
            sub.original_hire_date,
            sub.rehire_date,
            sub.academic_year,
            sub.termination_date,
            sub.status_reason,
            sub.academic_year_entrydate,
            sub.academic_year_exitdate,
            sub.kipp_alumni_status,
            lead(sub.academic_year_exitdate, 1) over (
                partition by sub.position_id order by sub.academic_year
            ) as academic_year_exitdate_next,
            w.business_unit,
            w.job_title,
            w. [location],
            w.home_department,
            scw.school_level,
            scw.reporting_school_id
        from
            (
                select
                    r.employee_number,
                    r.position_id,
                    r.preferred_first_name,
                    r.preferred_last_name,
                    r.race_ethnicity_reporting,
                    r.gender_reporting,
                    r.original_hire_date,
                    r.rehire_date,
                    r.status_reason,
                    r.kipp_alumni_status,
                    y.academic_year,
                    y.effective_date,
                    case
                        when (r.end_academic_year = y.academic_year)
                        then r.termination_date
                    end as termination_date,
                    case
                        when (r.start_academic_year = y.academic_year)
                        then r.position_start_date
                        else datefromparts(y.academic_year, 7, 1)
                    end as academic_year_entrydate,
                    coalesce(
                        case
                            when (r.end_academic_year = y.academic_year)
                            then r.termination_date
                        end,
                        datefromparts((y.academic_year + 1), 6, 30)
                    ) as academic_year_exitdate
                from roster as r
                inner join
                    years as y
                    on 
                        y.academic_year
                        between r.start_academic_year and r.end_academic_year
                    
            ) as sub
        left join
            people.employment_history_static as w
            on 
                sub.position_id = w.position_id
                and (
                    sub.effective_date
                    between w.effective_start_date and w.effective_end_date
                )
            
        left join
            people.school_crosswalk as scw
            on w. [location] = scw.site_name and scw._fivetran_deleted = 0
        where sub.academic_year_exitdate > sub.academic_year_entrydate
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
    [location] as primary_site,
    business_unit as legal_entity_name,
    reporting_school_id as primary_site_reporting_schoolid,
    school_level as primary_site_school_level,
    kipp_alumni_status,
    academic_year_exitdate_next as next_academic_year_exitdate,
    coalesce(academic_year_exitdate_next, termination_date) as attrition_exitdate,
    case
        when datediff(day, academic_year_entrydate, academic_year_exitdate) <= 0
        then 0
        when
            (
                academic_year_exitdate >= datefromparts(academic_year, 9, 1)
                and academic_year_entrydate
                <= (datefromparts((academic_year + 1), 4, 30))
            )
        then 1
        else 0
    end as is_denominator,
    case
        when
            coalesce(academic_year_exitdate_next, termination_date)
            < datefromparts((academic_year + 1), 9, 1)
        then 1
        else 0
    end as is_attrition,
    case
        when
            coalesce(rehire_date, original_hire_date)
            > coalesce(academic_year_exitdate_next, termination_date)
        then
            round(
                datediff(
                    day,
                    original_hire_date,
                    coalesce(academic_year_exitdate_next, termination_date)
                )
                / 365,
                0
            )
        else
            round(
                datediff(
                    day,
                    coalesce(rehire_date, original_hire_date),
                    coalesce(academic_year_exitdate_next, termination_date)
                )
                / 365,
                0
            )
    end as years_at_kipp
from scaffold
