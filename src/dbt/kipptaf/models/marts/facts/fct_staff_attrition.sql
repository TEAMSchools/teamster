with
    teammate_history as (
        select distinct
            effective_date_start,
            effective_date_end,
            assignment_status_effective_date,
            employee_number,
            assignment_status,
            assignment_status_reason,

            {{
                date_to_fiscal_year(
                    date_field="effective_date_start",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,
        from {{ ref("int_people__staff_roster_history") }}
        where
            (job_title != 'Intern' or assignment_status_reason != 'Internship Ended')
            and primary_indicator
    ),

    academic_years as (
        select distinct employee_number, academic_year, from teammate_history
    ),

    /* Foundation Attrition: latest record for staff not  */
    /* in an inactive status between 9/1 and 4/30 of an academic year  */
    foundation_year_cohort as (
        select
            ay.academic_year,

            th.employee_number,

            max(th.effective_date_start) as max_effective_date_start,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 4, 30)
            and th.effective_date_end >= date(ay.academic_year, 9, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
        group by ay.academic_year, th.employee_number
    ),

    /* Foundation Attrition: any staff not in terminated or deceased status  */
    /* on 9/1 of the following academic year  */
    foundation_returner_cohort as (
        select distinct ay.academic_year, th.employee_number,
        from academic_years as ay
        inner join
            teammate_history as th
            on date(ay.academic_year + 1, 9, 1)
            between th.effective_date_start and th.effective_date_end
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
    ),

    /* Foundation Attrition: first termination record within the window  */
    foundation_terminations as (
        select
            ay.academic_year,

            th.employee_number,
            th.assignment_status_reason as termination_reason,
            th.assignment_status_effective_date as termination_effective_date,

            row_number() over (
                partition by ay.academic_year, th.employee_number
                order by th.assignment_status_effective_date asc
            ) as rn,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.assignment_status_effective_date
            between date(ay.academic_year, 9, 1) and date(ay.academic_year + 1, 4, 30)
        where th.assignment_status in ('Terminated', 'Deceased')
    ),

    /* New Jersey Compliance Attrition: latest record for staff  */
    /* not in an inactive status between 7/1 and 6/30 of an academic year  */
    nj_year_cohort as (
        select
            ay.academic_year,

            th.employee_number,

            max(th.effective_date_start) as max_effective_date_start,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 6, 30)
            and th.effective_date_end >= date(ay.academic_year, 7, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
        group by ay.academic_year, th.employee_number
    ),

    /* New Jersey Compliance Attrition: any staff not in  */
    /* terminated or deceased status on 7/1 of the following academic year  */
    nj_returner_cohort as (
        select distinct ay.academic_year, th.employee_number,
        from academic_years as ay
        inner join
            teammate_history as th
            on date(ay.academic_year + 1, 7, 1)
            between th.effective_date_start and th.effective_date_end
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
    ),

    /* NJ Compliance: first termination record within the window  */
    nj_terminations as (
        select
            ay.academic_year,

            th.employee_number,
            th.assignment_status_reason as termination_reason,
            th.assignment_status_effective_date as termination_effective_date,

            row_number() over (
                partition by ay.academic_year, th.employee_number
                order by th.assignment_status_effective_date asc
            ) as rn,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.assignment_status_effective_date
            between date(ay.academic_year, 7, 1) and date(ay.academic_year + 1, 6, 30)
        where th.assignment_status in ('Terminated', 'Deceased')
    ),

    /* Recruitment Attrition: latest record for staff not in an  */
    /* inactive status between 9/1 and 8/31 of an academic year  */
    recruitment_year_cohort as (
        select
            ay.academic_year,

            th.employee_number,

            max(th.effective_date_start) as max_effective_date_start,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 8, 31)
            and th.effective_date_end >= date(ay.academic_year, 9, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
        group by ay.academic_year, th.employee_number
    ),

    /* Recruitment Attrition: any staff not in terminated or deceased  */
    /* status on 9/1 of the following academic year  */
    recruitment_returner_cohort as (
        select distinct ay.academic_year, th.employee_number,
        from academic_years as ay
        inner join
            teammate_history as th
            on date(ay.academic_year + 1, 9, 1)
            between th.effective_date_start and th.effective_date_end
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
    ),

    /* Recruitment: first termination record within the window  */
    recruitment_terminations as (
        select
            ay.academic_year,

            th.employee_number,
            th.assignment_status_reason as termination_reason,
            th.assignment_status_effective_date as termination_effective_date,

            row_number() over (
                partition by ay.academic_year, th.employee_number
                order by th.assignment_status_effective_date asc
            ) as rn,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.assignment_status_effective_date
            between date(ay.academic_year, 9, 1) and date(ay.academic_year + 1, 8, 31)
        where th.assignment_status in ('Terminated', 'Deceased')
    ),

    /* left joins to compare prior year to following year rosters  */
    final as (
        select
            fyc.academic_year,
            fyc.employee_number,

            'foundation' as attrition_type,

            if(frc.employee_number is null, true, false) as is_attrition,

            if(
                frc.employee_number is null, ft.termination_effective_date, null
            ) as termination_effective_date,

            if(
                frc.employee_number is null, ft.termination_reason, null
            ) as termination_reason,

            if(
                frc.employee_number is null,
                ft.termination_effective_date,
                date(fyc.academic_year + 1, 4, 30)
            ) as attrition_cutoff_date,
        from foundation_year_cohort as fyc
        left join
            foundation_returner_cohort as frc
            on fyc.employee_number = frc.employee_number
            and fyc.academic_year = frc.academic_year
        left join
            foundation_terminations as ft
            on fyc.employee_number = ft.employee_number
            and fyc.academic_year = ft.academic_year
            and ft.rn = 1

        union all

        select
            njyc.academic_year,
            njyc.employee_number,

            'nj_compliance' as attrition_type,

            if(njrc.employee_number is null, true, false) as is_attrition,

            if(
                njrc.employee_number is null, njt.termination_effective_date, null
            ) as termination_effective_date,

            if(
                njrc.employee_number is null, njt.termination_reason, null
            ) as termination_reason,

            if(
                njrc.employee_number is null,
                njt.termination_effective_date,
                date(njyc.academic_year + 1, 6, 30)
            ) as attrition_cutoff_date,
        from nj_year_cohort as njyc
        left join
            nj_returner_cohort as njrc
            on njyc.employee_number = njrc.employee_number
            and njyc.academic_year = njrc.academic_year
        left join
            nj_terminations as njt
            on njyc.employee_number = njt.employee_number
            and njyc.academic_year = njt.academic_year
            and njt.rn = 1

        union all

        select
            ryc.academic_year,
            ryc.employee_number,

            'recruitment' as attrition_type,

            if(rrc.employee_number is null, true, false) as is_attrition,

            if(
                rrc.employee_number is null, rt.termination_effective_date, null
            ) as termination_effective_date,

            if(
                rrc.employee_number is null, rt.termination_reason, null
            ) as termination_reason,

            if(
                rrc.employee_number is null,
                rt.termination_effective_date,
                date(ryc.academic_year + 1, 8, 31)
            ) as attrition_cutoff_date,
        from recruitment_year_cohort as ryc
        left join
            recruitment_returner_cohort as rrc
            on ryc.employee_number = rrc.employee_number
            and ryc.academic_year = rrc.academic_year
        left join
            recruitment_terminations as rt
            on ryc.employee_number = rt.employee_number
            and ryc.academic_year = rt.academic_year
            and rt.rn = 1
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["employee_number", "academic_year", "attrition_type"]
        )
    }} as staff_attrition_key,

    {{ dbt_utils.generate_surrogate_key(["employee_number"]) }} as staff_key,

    academic_year,
    employee_number,
    attrition_type,
    attrition_cutoff_date,
    is_attrition,
    termination_reason,
    termination_effective_date,
from final
