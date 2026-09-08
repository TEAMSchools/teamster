with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_fldoe__eoc"),
                    ref("stg_fldoe__fast"),
                    ref("stg_fldoe__science"),
                    source("fldoe", "stg_fldoe__fsa"),
                ]
            )
        }}
    ),

    transformed as (
        select
            test_code,
            academic_year,
            administration_window,
            season,
            discipline,
            assessment_subject,
            scale_score,
            achievement_level,
            is_proficient,

            cast(
                coalesce(assessment_grade, test_grade, enrolled_grade) as string
            ) as assessment_grade,

            coalesce(performance_level, achievement_level_int) as performance_level,
            coalesce(student_id, fleid) as student_id,

            coalesce(
                safe_cast(date_taken as date), safe.parse_date('%m/%d/%Y', date_taken)
            ) as test_date,

            regexp_extract(
                _dbt_source_relation, r'stg_fldoe__(\w+)'
            ) as assessment_name,
        from union_relations
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    fleid_lookup_raw as (
        select student_number, florida_education_identifier as fleid,
        from {{ ref("int_focus__students") }}
        where florida_education_identifier is not null
    ),

    fleid_lookup as (
        -- TODO: #3887 — 62 FLEIDs sit on more than one Focus student record;
        -- the lower student_number is the migrated one enrollments carry.
        {{
            dbt_utils.deduplicate(
                relation="fleid_lookup_raw",
                partition_by="fleid",
                order_by="student_number asc",
            )
        }}
    )

select
    t.* except (assessment_name),

    fl.student_number,

    'Actual' as results_type,
    'KTAF FL' as district_state,

    t.administration_window as `admin`,
    t.assessment_subject as `subject`,

    if(
        t.assessment_name = 'science', 'Science', upper(t.assessment_name)
    ) as assessment_name,

    case
        when t.assessment_subject like 'English Language Arts%'
        then 'Text Study'
        when t.assessment_subject in ('Algebra I', 'Algebra II', 'Geometry')
        then 'Mathematics'
        else t.assessment_subject
    end as illuminate_subject,

    case
        when t.performance_level = 1
        then 'Below/Far Below'
        when t.performance_level = 2
        then 'Approaching'
        when t.performance_level >= 3
        then 'At/Above'
    end as fast_aggregated_proficiency,

from transformed as t
left join fleid_lookup as fl on t.student_id = fl.fleid
