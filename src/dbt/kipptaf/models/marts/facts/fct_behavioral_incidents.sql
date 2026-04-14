with
    locations as (
        -- TODO: int_people__location_crosswalk has duplicate rows (#3633)
        select distinct
            location_deanslist_school_id,
            location_dagster_code_location,
            location_clean_name,
        from {{ ref("int_people__location_crosswalk") }}
        where
            not location_is_pathways
            and location_clean_name <> 'KIPP Whittier Elementary'
    ),

    enrollments as (
        select
            student_number,
            academic_year,
            entrydate,
            exitdate,
            _dbt_source_relation,

            row_number() over (
                partition by student_number, academic_year, _dbt_source_relation
                order by entrydate desc
            ) as rn,
        from {{ ref("base_powerschool__student_enrollments") }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["i.incident_id", "i._dbt_source_relation"]) }}
    as behavioral_incident_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_relation",
                "i.create_ts_academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    cast(i.create_ts_date as date) as date_key,

    enr.student_number,
    i.create_ts_academic_year as academic_year,

    i.incident_id,
    i.category as incident_category,
    i.category_tier,
    i.infraction,
    i.location as incident_location,
    i.context as incident_context,
    i.status as incident_status,
    i.referral_tier,

    i.create_lastfirst as referring_staff_name,
    i.create_by as referring_staff_id,

    i.is_referral,
    i.is_active,

    cast(i.create_ts_date as date) as incident_date,
    cast(i.close_ts_date as date) as close_date,
    cast(i.return_date_date as date) as return_date,
from {{ ref("int_deanslist__incidents") }} as i
inner join
    enrollments as enr
    on i.student_school_id = enr.student_number
    and i.create_ts_academic_year = enr.academic_year
    and {{ union_dataset_join_clause(left_alias="i", right_alias="enr") }}
    and enr.rn = 1
left join
    locations as loc
    on i.school_id = loc.location_deanslist_school_id
    and {{ extract_code_location("i") }} = loc.location_dagster_code_location
