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
    )

select
    *,

    'NJGPA' as assessment_name,

    if(testperformancelevel = 2, true, false) as is_proficient,

    case
        testperformancelevel
        when 2
        then 'Graduation Ready'
        when 1
        then 'Not Yet Graduation Ready'
    end as testperformancelevel_text,

    coalesce(
        case
            when
                coalesce(
                    unit1onlineteststartdatetime,
                    unit2onlineteststartdatetime,
                    unit3onlineteststartdatetime
                )
                is not null
            then
                date(
                    least(
                        coalesce(
                            safe_cast(unit1onlineteststartdatetime as timestamp),
                            cast('9999-12-31' as timestamp)
                        ),
                        coalesce(
                            safe_cast(unit2onlineteststartdatetime as timestamp),
                            cast('9999-12-31' as timestamp)
                        ),
                        coalesce(
                            safe_cast(unit3onlineteststartdatetime as timestamp),
                            cast('9999-12-31' as timestamp)
                        )
                    )
                )
        end,
        safe_cast(paperattemptcreatedate as date)
    ) as test_date,

from njgpa
