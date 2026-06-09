with
    njgpa as (
        select
            firstname,
            lastorsurname,
            assessmentgrade,
            assessmentyear,
            `period`,
            `subject`,
            testcode,
            studenttestuuid,
            studentwithdisabilities,
            hispanicorlatinoethnicity,
            americanindianoralaskanative,
            asian,
            blackorafricanamerican,
            nativehawaiianorotherpacificislander,
            white,
            twoormoreraces,

            cast(localstudentidentifier as int) as localstudentidentifier,
            cast(statestudentidentifier as int) as statestudentidentifier,

            cast(testperformancelevel as numeric) as testperformancelevel,
            cast(testscalescore as numeric) as testscalescore,
            cast(testscorecomplete as numeric) as testscorecomplete,

            cast(
                cast(staffmemberidentifier as numeric) as int
            ) as staffmemberidentifier,
            cast(cast(testadministrator as numeric) as int) as testadministrator,

            cast(
                nullif(trim(testcsemprobablerange), '') as numeric
            ) as testcsemprobablerange,
            cast(nullif(trim(testreadingcsem), '') as numeric) as testreadingcsem,
            cast(
                nullif(trim(testreadingscalescore), '') as numeric
            ) as testreadingscalescore,
            cast(nullif(trim(testwritingcsem), '') as numeric) as testwritingcsem,
            cast(
                nullif(trim(testwritingscalescore), '') as numeric
            ) as testwritingscalescore,

            unit1onlineteststartdatetime,
            unit1onlinetestenddatetime,
            unit2onlineteststartdatetime,
            unit2onlinetestenddatetime,
            unit3onlineteststartdatetime,
            unit3onlinetestenddatetime,
            paperattemptcreatedate,

            cast(left(assessmentyear, 4) as int) as academic_year,

            cast(regexp_extract(assessmentgrade, r'Grade\s(\d+)') as int) as test_grade,

            coalesce(multilinguallearnerml, englishlearnerel) as englishlearnerel,

            if(`period` = 'FallBlock', 'Fall', `period`) as `admin`,
            if(`period` = 'FallBlock', 'Fall', `period`) as season,
            if(`subject` = 'Mathematics', 'Math', 'ELA') as discipline,

        from {{ source("pearson", "src_pearson__njgpa") }}
        where summativeflag = 'Y' and testattemptednessflag = 'Y'
    ),

    unit_test_starts as (
        select
            *,

            safe_cast(
                unit1onlineteststartdatetime as timestamp
            ) as unit1_start_timestamp,
            safe_cast(
                unit2onlineteststartdatetime as timestamp
            ) as unit2_start_timestamp,
            safe_cast(
                unit3onlineteststartdatetime as timestamp
            ) as unit3_start_timestamp,

        from njgpa
    )

select
    * except (unit1_start_timestamp, unit2_start_timestamp, unit3_start_timestamp),

    'NJGPA' as assessment_name,

    if(testperformancelevel = 2, true, false) as is_proficient,

    coalesce(
        (
            select date(min(unit_start)),
            from
                unnest(
                    [
                        unit1_start_timestamp,
                        unit2_start_timestamp,
                        unit3_start_timestamp
                    ]
                ) as unit_start
        ),
        safe_cast(paperattemptcreatedate as date)
    ) as test_date,

    case
        testperformancelevel
        when 2
        then 'Graduation Ready'
        when 1
        then 'Not Yet Graduation Ready'
    end as testperformancelevel_text,

from unit_test_starts
