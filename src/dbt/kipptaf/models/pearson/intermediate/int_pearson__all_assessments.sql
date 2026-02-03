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
    u.`subject`,
    u.testcode,
    u.studenttestuuid,
    u.test_grade,
    u.testperformancelevel_text,
    u.testperformancelevel,
    u.testscalescore,
    u.twoormoreraces,
    u.white,

    'Actual' as results_type,
    'KTAF NJ' as district_state,

    cast(u.statestudentidentifier as string) as statestudentidentifier,

    coalesce(u.studentwithdisabilities in ('504', 'B'), false) as is_504,

    coalesce(x.student_number, u.localstudentidentifier) as localstudentidentifier,

    case
        u.testcode
        when 'SC05'
        then 'SCI05'
        when 'SC08'
        then 'SCI08'
        when 'SC11'
        then 'SCI11'
        else u.testcode
    end as aligned_test_code,

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
        when u.`subject` like 'English Language Arts%'
        then 'Text Study'
        when u.`subject` in ('Algebra I', 'Algebra II', 'Geometry')
        then 'Mathematics'
        else u.`subject`
    end as illuminate_subject,

    case
        when u.assessment_name = 'NJSLA' and u.testperformancelevel <= 2
        then 'Below/Far Below'
        when u.assessment_name = 'NJSLA' and u.testperformancelevel = 3
        then 'Approaching'
        when u.assessment_name = 'NJSLA' and u.testperformancelevel >= 4
        then 'At/Above'
    end as njsla_aggregated_proficiency,

    if(u.englishlearnerel = 'Y', true, false) as lep_status,

    if(u.studentwithdisabilities in ('IEP', 'B'), 'Has IEP', 'No IEP') as iep_status,

    if(u.`period` = 'FallBlock', 'Fall', u.`period`) as `admin`,

    if(u.`period` = 'FallBlock', 'Fall', u.`period`) as season,

    if(
        u.`subject` = 'English Language Arts/Literacy',
        'English Language Arts',
        u.`subject`
    ) as aligned_subject,

    if(u.is_proficient, 1, 0) as is_proficient_int,

from union_relations as u
left join
    {{ ref("stg_google_sheets__pearson__student_crosswalk") }} as x
    on u.studenttestuuid = x.student_test_uuid
