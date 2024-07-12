with
    union_relations as (
        {{
            dbt_utils.union_relations(
                source_column_name="_dbt_source_relation_2",
                relations=[
                    ref("stg_pearson__parcc"),
                    ref("stg_pearson__njsla"),
                    ref("stg_pearson__njsla_science"),
                    ref("stg_pearson__njgpa"),
                ],
                include=[
                    "_dbt_source_relation",
                    "academic_year",
                    "americanindianoralaskanative",
                    "asian",
                    "assessment_name",
                    "assessmentgrade",
                    "assessmentyear",
                    "blackorafricanamerican",
                    "englishlearnerel",
                    "hispanicorlatinoethnicity",
                    "is_proficient",
                    "nativehawaiianorotherpacificislander",
                    "period",
                    "statestudentidentifier",
                    "studentwithdisabilities",
                    "subject_area",
                    "subject",
                    "testcode",
                    "testperformancelevel_text",
                    "testperformancelevel",
                    "testscalescore",
                    "twoormoreraces",
                    "white",
                ],
            )
        }}
    ),

    with_translations as (
        select  -- noqa: AM04
            * except (statestudentidentifier, _dbt_source_relation_2),

            safe_cast(statestudentidentifier as string) as statestudentidentifier,

            safe_cast(
                regexp_extract(assessmentgrade, r'Grade\s(\d+)') as int
            ) as test_grade,

            upper(
                regexp_extract(_dbt_source_relation, r'__(\w+)`$')
            ) as assessment_name,

            coalesce(studentwithdisabilities in ('504', 'B'), false) as is_504,

            if(englishlearnerel = 'Y', true, false) as lep_status,

            if(`period` = 'FallBlock', 'Fall', `period`) as `admin`,

            if(`period` = 'FallBlock', 'Fall', `period`) as season,

            case
                when
                    `subject`
                    in ('English Language Arts', 'English Language Arts/Literacy')
                then 'ELA'
                when `subject` in ('Mathematics', 'Algebra I', 'Algebra II', 'Geometry')
                then 'Math'
                when `subject` = 'Science'
                then 'Science'
            end as subject_area,

            case
                testcode
                when 'SC05'
                then 'SCI05'
                when 'SC08'
                then 'SCI08'
                when 'SC11'
                then 'SCI11'
                else testcode
            end as test_code,

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
                when `subject` = 'Science' and testperformancelevel >= 3
                then true
                when testcode in ('MATGP', 'ELAGP') and testperformancelevel = 2
                then true
                when testperformancelevel >= 4
                then true
                when testperformancelevel < 4
                then false
            end as is_proficient,

            case
                when studentwithdisabilities in ('IEP', 'B')
                then 'Has IEP'
                else 'No IEP'
            end as iep_status,

            case
                when twoormoreraces = 'Y'
                then 'T'
                when hispanicorlatinoethnicity = 'Y'
                then 'H'
                when americanindianoralaskanative = 'Y'
                then 'I'
                when asian = 'Y'
                then 'A'
                when blackorafricanamerican = 'Y'
                then 'B'
                when nativehawaiianorotherpacificislander = 'Y'
                then 'P'
                when white = 'Y'
                then 'W'
            end as race_ethnicity,
        from union_relations
    )

select
    _dbt_source_relation,
    assessment_name,
    statestudentidentifier,
    assessmentyear,
    academic_year,
    `period`,
    testcode,
    `subject`,
    subject_area,
    assessmentgrade,
    testscalescore,
    testperformancelevel,
    testperformancelevel_text,
    is_proficient,
    studentwithdisabilities,
    englishlearnerel,
    twoormoreraces,
    americanindianoralaskanative,
    asian,
    blackorafricanamerican,
    hispanicorlatinoethnicity,
    nativehawaiianorotherpacificislander,
    white,

    case
        when testcode in ('ELAGP', 'MATGP') and testperformancelevel = 2
        then 'Graduation Ready'
        when testcode in ('ELAGP', 'MATGP') and testperformancelevel = 1
        then 'Not Yet Graduation Ready'
        else testperformancelevel_text
    end as performance_band,

from with_translations
