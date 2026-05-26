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
                    "_dbt_source_project",
                    "academic_year",
                    "administration_period",
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
                    "module_code",
                    "nativehawaiianorotherpacificislander",
                    "period",
                    "statestudentidentifier",
                    "localstudentidentifier",
                    "firstname",
                    "lastorsurname",
                    "studentwithdisabilities",
                    "subject",
                    "subject_area",
                    "testcode",
                    "studenttestuuid",
                    "testscorecomplete",
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
    u._dbt_source_project,
    u.academic_year,
    u.administration_period,
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
    u.module_code,
    u.nativehawaiianorotherpacificislander,
    u.period,
    u.firstname,
    u.lastorsurname,
    u.subject,
    u.subject_area,
    u.testcode,
    u.studenttestuuid,
    u.test_grade,
    u.testperformancelevel_text,
    u.testperformancelevel,
    u.testscalescore,
    u.testscorecomplete,
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

    case
        u.assessment_name
        when 'PARCC'
        then 'state_nj_parcc'
        when 'NJSLA'
        then 'state_nj_njsla'
        when 'NJSLA Science'
        then 'state_nj_njsla_science'
        when 'NJGPA'
        then 'state_nj_njgpa'
    end as assessment_type,

from union_relations as u
left join
    {{ ref("stg_google_sheets__pearson__student_crosswalk") }} as x
    on u.studenttestuuid = x.student_test_uuid
