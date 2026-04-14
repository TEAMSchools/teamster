with
    locations as (
        select distinct location_powerschool_school_id, location_clean_name,
        from {{ ref("int_people__location_crosswalk") }}
        where
            not location_is_pathways
            and location_clean_name <> 'KIPP Whittier Elementary'
    ),

    goals_with_school as (
        select
            g.academic_year,
            g.school_id,
            g.state_assessment_code,
            g.illuminate_subject_area,
            g.grade_level,
            g.grade_goal,
            g.school_goal,
            g.region_goal,
            g.organization_goal,
            g.grade_band_goal,
            g.assessment_band_goal,

            s.school_level,

            initcap(regexp_extract(s._dbt_source_relation, r'kipp(\w+)_')) as region,
        from {{ ref("stg_google_sheets__assessments__academic_goals") }} as g
        inner join
            {{ ref("stg_powerschool__schools") }} as s on g.school_id = s.school_number
    ),

    deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="goals_with_school",
                partition_by=(
                    "academic_year, school_id, "
                    "state_assessment_code, grade_level, "
                    "illuminate_subject_area"
                ),
                order_by="school_goal desc",
            )
        }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "d.academic_year",
                "d.school_id",
                "d.state_assessment_code",
                "d.grade_level",
                "d.illuminate_subject_area",
            ]
        )
    }} as assessment_target_key,

    {{ dbt_utils.generate_surrogate_key(["loc.location_clean_name"]) }} as location_key,

    d.academic_year,
    d.school_id,
    d.state_assessment_code,
    d.illuminate_subject_area,
    d.grade_level as assessment_grade_level,
    d.grade_goal,
    d.school_goal,
    d.region_goal,
    d.organization_goal,
    d.grade_band_goal,
    d.assessment_band_goal,
    d.school_level,
    d.region,
from deduplicated as d
left join locations as loc on d.school_id = loc.location_powerschool_school_id
