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
                    "localstudentidentifier",
                    "firstname",
                    "lastorsurname",
                    "studentwithdisabilities",
                    "subject",
                    "testcode",
                    "studenttestuuid",
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
    * except (
        localstudentidentifier,
        statestudentidentifier,
        _dbt_source_relation_2,
        test_academic_year,
        state_student_identifier,
        test_code,
        student_number
    ),

    safe_cast(u.statestudentidentifier as string) as statestudentidentifier,

    coalesce(u.studentwithdisabilities in ('504', 'B'), false) as is_504,

    if(
        x.student_number is null, u.localstudentidentifier, x.student_number
    ) as localstudentidentifier,

    if(u.englishlearnerel = 'Y', true, false) as lep_status,

    if(u.studentwithdisabilities in ('IEP', 'B'), 'Has IEP', 'No IEP') as iep_status,

    case
        when u.twoormoreraces = 'Y'
        then 'T'
        when u.hispanicorlatinoethnicity = 'Y'
        then 'H'
        when u.americanindianoralaskanative = 'Y'
        then 'I'
        when u.asian = 'Y'
        then 'A'
        when u.blackorafricanamerican = 'Y'
        then 'B'
        when u.nativehawaiianorotherpacificislander = 'Y'
        then 'P'
        when u.white = 'Y'
        then 'W'
    end as race_ethnicity,

from union_relations as u
left join
    {{ ref("stg_assessments__student_number_xwalk") }} as x
    on u.academic_year = x.test_academic_year
    and u.statestudentidentifier = x.state_student_identifier
    and u.testcode = x.test_code
