with
    finalsite_ids as (
        select
            _dbt_source_project,
            finalsite_enrollment_id,
            cast(focus_student_id_prefixed as int) as focus_student_id,
        from {{ ref("int_finalsite__contact_id_attributes") }}
    ),

    enrollment as (
        select
            s._dbt_source_relation,
            s._dbt_source_project,
            s.student_id as student_number,
            s.first_name as student_first_name,
            s.last_name as student_last_name,
            s.florida_education_identifier as fteid,
            s.student_e_mail_address as student_email,

            e.id as student_enrollment_id,
            e.syear as academic_year,
            e.school_id as schoolid,
            e.start_date as startdate,

            sch.state,

            loc.powerschool_school_id as ps_schoolid,
            loc.location_name as school,
            loc.abbreviation as school_abbreviation,
            loc.reporting_school_id as reporting_schoolid,
            loc.location_region as region_official_name,
            loc.deanslist_school_id,

            ec.short_name as entrycode,

            dc.short_name as exitcode,

            f.finalsite_enrollment_id,

            fd.first_day_of_school,

            'KTAF' as district,

            cast(s.birthdate as date) as dob,

            concat(s.last_name, ', ', s.first_name) as student_name,

            {{ extract_region("s") }} as region,

            cast(e.syear as string)
            || '-'
            || right(cast(e.syear + 1 as string), 2) as academic_year_display,

            coalesce(e.end_date, date(e.syear + 1, 6, 30)) as exitdate,

            case
                g.short_name
                when 'PK'
                then -1
                when 'KG'
                then 0
                else cast(regexp_extract(g.short_name, r'\d+') as int)
            end as grade_level,

            case
                when dc.grad_type = 'graduated'
                then 3
                when e.drop_code is not null
                then 2
                else 0
            end as enroll_status,

            case
                slo.code when 'E' then 'ES' when 'M' then 'MS' when 'H' then 'HS'
            end as school_level,

        from {{ ref("stg_focus__students") }} as s
        inner join
            {{ ref("stg_focus__student_enrollment") }} as e
            on s.student_id = e.student_id
            and s._dbt_source_project = e._dbt_source_project
        left join
            {{ ref("stg_focus__schools") }} as sch
            on e.school_id = sch.id
            and e._dbt_source_project = sch._dbt_source_project
        left join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on sch.school_number = loc.focus_school_id
        left join
            {{ ref("stg_focus__custom_field_select_options") }} as slo
            on sch.school_level = slo.id
            and slo.source_class = 'CustomField'
            and sch._dbt_source_project = slo._dbt_source_project
        left join
            {{ ref("stg_focus__school_gradelevels") }} as g
            on e.grade_id = g.id
            and e.school_id = g.school_id
            and e._dbt_source_project = g._dbt_source_project
            and g.short_name != '30'
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as ec
            on e.enrollment_code = ec.id
            and e._dbt_source_project = ec._dbt_source_project
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as dc
            on e.drop_code = dc.id
            and e._dbt_source_project = dc._dbt_source_project
        left join
            finalsite_ids as f
            on e.student_id = f.focus_student_id
            and e._dbt_source_project = f._dbt_source_project
        left join
            {{ ref("int_focus__school_year_first_day") }} as fd on e.syear = fd.syear
    ),

    with_flags as (
        select
            *,

            concat(region, school_level) as region_school_level,

            if(startdate <= first_day_of_school, true, false) as is_enrolled_fdos,

            if(
                date(academic_year, 10, 1) between startdate and exitdate, true, false
            ) as is_enrolled_oct01,

            if(
                date(academic_year, 10, 15) between startdate and exitdate, true, false
            ) as is_enrolled_oct15,

            if(
                date(academic_year + 1, 3, 15) between startdate and exitdate,
                true,
                false
            ) as is_enrolled_mar15,

            if(exitdate < first_day_of_school, true, false) as is_pre_year_withdrawal,

            row_number() over (
                partition by student_number, academic_year
                order by academic_year desc, exitdate desc
            ) as rn_year,
        from enrollment
    ),

    with_year_counts as (
        select
            *,

            row_number() over (
                partition by student_number, schoolid, rn_year
                order by academic_year asc, exitdate asc
            ) as year_in_school,

            row_number() over (
                partition by student_number, rn_year
                order by academic_year asc, exitdate asc
            ) as year_in_network,
        from with_flags
    )

select
    * except (year_in_school, year_in_network),

    if(rn_year = 1, year_in_school, null) as year_in_school,

    if(rn_year = 1, year_in_network, null) as year_in_network,

from with_year_counts
