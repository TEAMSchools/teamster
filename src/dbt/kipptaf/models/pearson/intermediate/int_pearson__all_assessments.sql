with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_pearson__parcc"),
                    ref("stg_pearson__njsla"),
                    ref("stg_pearson__njsla_science"),
                    ref("stg_pearson__njgpa"),
                ],
                exclude=["_dbt_source_relation"],
            )
        }}
    ),

    with_translations as (

        select  -- noqa: AM04
            * except (statestudentidentifier),
            safe_cast(statestudentidentifier as string) as statestudentidentifier,
            upper(
                regexp_extract(_dbt_source_relation, r'__(\w+)`$')
            ) as assessment_name,
            case
                when
                    subject
                    in ('English Language Arts', 'English Language Arts/Literacy')
                then 'ELA'
                when subject in ('Mathematics', 'Algebra I', 'Algebra II', 'Geometry')
                then 'Math'
                when subject = 'Science'
                then 'Science'
            end as subject_area,
            case
                testperformancelevel
                when 5
                then 'Exceeded Expectations'
                when 4
                then 'Met Expectations'
                when 3
                then 'Approached Expectations'
                when 2
                then 'Partially Met Expectations'
                when 1
                then 'Did Not Yet Meet Expectations'
            end as testperformancelevel_text,
            case
                when subject = 'Science' and testperformancelevel >= 3
                then true
                when testcode in ('MATGP', 'ELAGP') and testperformancelevel = 2
                then true
                when testperformancelevel >= 4
                then true
                when testperformancelevel < 4
                then false
            end as is_proficient,

        from union_relations

    )

select
    *,
    row_number() over (
        partition by statestudentidentifier, assessment_name, testcode
        order by testscalescore desc
    ) as rn_highest_student_test,
from with_translations
