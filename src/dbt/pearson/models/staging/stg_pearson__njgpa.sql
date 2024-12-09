{%- set src_njgpa = source("pearson", "src_pearson__njgpa") -%}

select
    statestudentidentifier,
    localstudentidentifier,

    assessmentgrade,
    assessmentyear,
    `period`,
    `subject`,
    testcode,
    testperformancelevel,
    testscalescore,
    testscorecomplete,

    studentwithdisabilities,
    englishlearnerel,
    hispanicorlatinoethnicity,
    americanindianoralaskanative,
    asian,
    blackorafricanamerican,
    nativehawaiianorotherpacificislander,
    white,
    twoormoreraces,

    'NJGPA' as assessment_name,

    cast(left(assessmentyear, 4) as int) as academic_year,

    cast(regexp_extract(assessmentgrade, r'Grade\s(\d+)') as int) as test_grade,

    coalesce(
        staffmemberidentifier.long_value,
        cast(staffmemberidentifier.double_value as int)
    ) as staffmemberidentifier,
    coalesce(
        testadministrator.long_value, cast(testadministrator.double_value as int)
    ) as testadministrator,

    coalesce(
        testcsemprobablerange.double_value,
        cast(testcsemprobablerange.string_value as numeric)
    ) as testcsemprobablerange,
    coalesce(
        testreadingcsem.double_value, cast(testreadingcsem.string_value as numeric)
    ) as testreadingcsem,
    coalesce(
        testreadingscalescore.double_value,
        cast(testreadingscalescore.string_value as numeric)
    ) as testreadingscalescore,
    coalesce(
        testwritingcsem.double_value, cast(testwritingcsem.string_value as numeric)
    ) as testwritingcsem,
    coalesce(
        testwritingscalescore.double_value,
        cast(testwritingscalescore.string_value as numeric)
    ) as testwritingscalescore,

    if(`subject` = 'Mathematics', 'Math', 'ELA') as discipline,

    if(`period` = 'FallBlock', 'Fall', `period`) as `admin`,

    if(`period` = 'FallBlock', 'Fall', `period`) as season,

    if(testperformancelevel = 2, true, false) as is_proficient,

    case
        testperformancelevel
        when 2
        then 'Graduation Ready'
        when 1
        then 'Not Yet Graduation Ready'
    end as testperformancelevel_text,
from {{ src_njgpa }}
where summativeflag = 'Y' and testattemptednessflag = 'Y'
