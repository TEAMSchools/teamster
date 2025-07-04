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
                    "is_bl_fb",
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

select
    u._dbt_source_relation,
    u.academic_year,
    u.americanindianoralaskanative,
    u.asian,
    u.assessment_name,
    u.assessmentgrade,
    u.assessmentyear,
    u.blackorafricanamerican,
    u.discipline,
    u.hispanicorlatinoethnicity,
    u.is_proficient,
    u.is_bl_fb,
    u.nativehawaiianorotherpacificislander,
    u.period,
    u.firstname,
    u.lastorsurname,
    u.subject,
    u.testcode,
    u.studenttestuuid,
    u.test_grade,
    u.testperformancelevel_text,
    u.testperformancelevel,
    u.testscalescore,
    u.twoormoreraces,
    u.white,

    cast(u.statestudentidentifier as string) as statestudentidentifier,

    coalesce(u.studentwithdisabilities in ('504', 'B'), false) as is_504,

    coalesce(x.student_number, u.localstudentidentifier) as localstudentidentifier,

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
    {{ ref("stg_pearson__student_crosswalk") }} as x
    on u.studenttestuuid = x.student_test_uuid
