select
    statestudentidentifier,
    localstudentidentifier,
    firstname,
    lastorsurname,

    assessmentgrade,
    assessmentyear,
    `period`,
    `subject`,
    testcode,
    studenttestuuid,
    testperformancelevel,
    testscalescore,
    testscorecomplete,

    studentwithdisabilities,
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

    coalesce(multilinguallearnerml, englishlearnerel) as englishlearnerel,

    coalesce(
        staffmemberidentifier.long_value,
        cast(staffmemberidentifier.double_value as int)
    ) as staffmemberidentifier,
    coalesce(
        testadministrator.long_value, cast(testadministrator.double_value as int)
    ) as testadministrator,

    coalesce(
        testcsemprobablerange.double_value,
        safe_cast(trim(testcsemprobablerange.string_value) as numeric)
    ) as testcsemprobablerange,
    coalesce(
        testreadingcsem.double_value,
        safe_cast(trim(testreadingcsem.string_value) as numeric)
    ) as testreadingcsem,
    coalesce(
        testreadingscalescore.double_value,
        safe_cast(trim(testreadingscalescore.string_value) as numeric)
    ) as testreadingscalescore,
    coalesce(
        testwritingcsem.double_value,
        safe_cast(trim(testwritingcsem.string_value) as numeric)
    ) as testwritingcsem,
    coalesce(
        testwritingscalescore.double_value,
        safe_cast(trim(testwritingscalescore.string_value) as numeric)
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
from {{ source("pearson", "src_pearson__njgpa") }}
where summativeflag = 'Y' and testattemptednessflag = 'Y'
