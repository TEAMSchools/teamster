{{ config(enabled=False) }}

/*
School staff assigned to primary school only
Campus staff assigned to all schools at campus
*/
select
    cast(coalesce(ccw.ps_school_id, df.primary_site_schoolid) as varchar(25)) as [
        school_id
    ],
    df.ps_teachernumber as staff_id,
    df.userprincipalname as staff_email,
    df.preferred_first_name as first_name,
    df.preferred_last_name as last_name,
    df.primary_on_site_department as department,
    'School Admin' as title,
    df.samaccountname as username,
    null as password,
    case
        when df.primary_on_site_department = 'Operations' then 'School Tech Lead'
    end as role
from people.staff_crosswalk_static as df
left join
    people.campus_crosswalk as ccw
    on df.primary_site = ccw.campus_name
    and ccw._fivetran_deleted = 0
    and ccw.is_pathways = 0
where
    df.status not in ('TERMINATED', 'PRESTART')
    and df.primary_on_site_department not in ('Data', 'Teaching and Learning')
    and coalesce(ccw.ps_school_id, df.primary_site_schoolid) != 0

union all

/* T&L/EDs/Data to all schools under CMO */
select
    cast(sch.school_number as varchar(25)) as school_id,
    df.ps_teachernumber as staff_id,
    df.userprincipalname as staff_email,
    df.preferred_first_name as first_name,
    df.preferred_last_name as last_name,
    df.primary_on_site_department as department,
    'School Admin' as title,
    df.samaccountname as username,
    null as password,
    case
        when df.primary_on_site_department = 'Operations' then 'School Tech Lead'
    end as role
from people.staff_crosswalk_static as df
inner join powerschool.schools as sch on (sch.state_excludefromreporting = 0)
where
    df.status not in ('TERMINATED', 'PRESTART')
    and df.legal_entity_name = 'KIPP TEAM and Family Schools Inc.'
    and (
        df.primary_on_site_department in ('Data', 'Teaching and Learning')
        or df.primary_job in ('Executive Director', 'Managing Director')
    )

union all

/* All region */
select
    cast(sch.school_number as varchar(25)) as school_id,
    df.ps_teachernumber as staff_id,
    df.userprincipalname as staff_email,
    df.preferred_first_name as first_name,
    df.preferred_last_name as last_name,
    df.primary_on_site_department as department,
    'School Admin' as title,
    df.samaccountname as username,
    null as password,
    case
        when df.primary_on_site_department = 'Operations' then 'School Tech Lead'
    end as role
from people.staff_crosswalk_static as df
inner join
    powerschool.schools as sch
    on df.db_name = sch.db_name
    and sch.state_excludefromreporting = 0
where
    df.status not in ('TERMINATED', 'PRESTART')
    and (
        df.primary_job in (
            'Assistant Superintendent',
            'Head of Schools',
            'Head of Schools in Residence'
        )
        or (
            df.primary_on_site_department = 'Special Education'
            and df.primary_job like '%Director%'
        )
    )

union all

/* All NJ */
select
    cast(sch.school_number as varchar(25)) as school_id,
    df.ps_teachernumber as staff_id,
    df.userprincipalname as staff_email,
    df.preferred_first_name as first_name,
    df.preferred_last_name as last_name,
    df.primary_on_site_department as department,
    'School Admin' as title,
    df.samaccountname as username,
    null as password,
    case
        when df.primary_on_site_department = 'Operations' then 'School Tech Lead'
    end as role
from adsi.group_membership as adg
inner join
    people.staff_crosswalk_static as df
    on adg.employee_number = df.df_employee_number
    and df.status not in ('TERMINATED', 'PRESTART')
inner join
    powerschool.schools as sch
    on sch.schoolstate = 'NJ'
    and sch.state_excludefromreporting = 0
where adg.group_cn = 'Group Staff NJ Regional'
