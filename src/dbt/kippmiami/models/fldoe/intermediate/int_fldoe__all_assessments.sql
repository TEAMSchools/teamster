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
        select
            t.student_id as fleid,
            t.academic_year,

            s.student_number,

            e.student_id is not null as is_enrolled,
        from transformed as t
        inner join
            {{ ref("int_focus__students") }} as s
            on t.student_id = s.florida_education_identifier
        left join
            {{ ref("int_focus__student_enrollment") }} as e
            on s.student_id = e.student_id
            and t.academic_year = e.syear
    ),

    fleid_lookup as (
        -- some FLEIDs sit on more than one Focus record (#5584): prefer the one
        -- enrolled that year, else the lower student_number
        {{
            dbt_utils.deduplicate(
                relation="fleid_lookup_raw",
                partition_by="fleid, academic_year",
                order_by="is_enrolled desc, student_number asc",
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
        when t.performance_level = 1
        then 'Below/Far Below'
        when t.performance_level = 2
        then 'Approaching'
        when t.performance_level >= 3
        then 'At/Above'
    end as fast_aggregated_proficiency,

from transformed as t
left join
    fleid_lookup as fl on t.student_id = fl.fleid and t.academic_year = fl.academic_year
