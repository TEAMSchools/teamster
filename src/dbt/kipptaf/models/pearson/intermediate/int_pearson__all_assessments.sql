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
                    "discipline",
                    "englishlearnerel",
                    "hispanicorlatinoethnicity",
                    "is_proficient",
                    "nativehawaiianorotherpacificislander",
                    "period",
                    "statestudentidentifier",
                    "studentwithdisabilities",
                    "subject",
                    "testcode",
                    "test_grade",
                    "testperformancelevel_text",
                    "testperformancelevel",
                    "testscalescore",
                    "twoormoreraces",
                    "white",
                ],
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (statestudentidentifier, _dbt_source_relation_2),

    safe_cast(statestudentidentifier as string) as statestudentidentifier,

    coalesce(studentwithdisabilities in ('504', 'B'), false) as is_504,

    if(englishlearnerel = 'Y', true, false) as lep_status,
    if(studentwithdisabilities in ('IEP', 'B'), 'Has IEP', 'No IEP') as iep_status,

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

    regexp_extract(_dbt_source_relation, r'__(\w+)`$') as assessment_name,
from union_relations
