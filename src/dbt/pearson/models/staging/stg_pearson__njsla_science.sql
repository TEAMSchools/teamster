with
    njsla_science as (
        select
            * except (
                accountabledistrictcode,
                accountableorganizationaltype,
                accountableschoolcode,
                federalraceethnicity,
                filler,
                gradelevelwhenassessed,
                shipreportdistrictcode,
                shipreportschoolcode,
                statestudentidentifier,
                testingdistrictcode,
                testingorganizationaltype,
                testingschoolcode,
                colorcontrast,
                elaconstructedresponse,
                elalconstructedresponse,
                elalselectedresponseortechnologyenhanceditems,
                elaselectedresponseortechnologyenhanceditems,
                emergencyaccommodation,
                englishlearneraccommodatedresponses,
                homelessprimarynighttimeresidence,
                humanreaderorhumansigner,
                localstudentidentifier,
                mathematics_scienceaccommodatedresponse,
                mathematicsscienceaccommodatedresponse,
                multilinguallearneraccommodatedresponses,
                nottestedreason,
                paperpcr1,
                paperpcr2,
                papersection1numberofattempteditems,
                papersection1totaltestitems,
                papersection2numberofattempteditems,
                papersection2totaltestitems,
                papersection3numberofattempteditems,
                papersection3totaltestitems,
                papersection4numberofattempteditems,
                papersection4totaltestitems,
                percentofitemsattempted,
                specialeducationplacement,
                staffmemberidentifier,
                subclaim1category,
                subclaim2category,
                subclaim3category,
                subclaim4category,
                subclaim5category,
                testadministrator,
                testcsemprobablerange,
                testperformancelevel,
                testreadingcsem,
                testreadingscalescore,
                testscalescore,
                testscorecomplete,
                testwritingcsem,
                testwritingscalescore,
                texttospeech,
                totaltestitems,
                totaltestitemsattempted,
                unit1numberofattempteditems,
                unit1totaltestitems,
                unit2numberofattempteditems,
                unit2totaltestitems,
                unit3numberofattempteditems,
                unit3totaltestitems,
                voidscorereason
            ),

            cast(accountabledistrictcode as int) as accountabledistrictcode,
            cast(accountableorganizationaltype as int) as accountableorganizationaltype,
            cast(accountableschoolcode as int) as accountableschoolcode,
            cast(federalraceethnicity as int) as federalraceethnicity,
            cast(gradelevelwhenassessed as int) as gradelevelwhenassessed,
            cast(shipreportdistrictcode as int) as shipreportdistrictcode,
            cast(shipreportschoolcode as int) as shipreportschoolcode,
            cast(statestudentidentifier as int) as statestudentidentifier,
            cast(testingdistrictcode as int) as testingdistrictcode,
            cast(testingorganizationaltype as int) as testingorganizationaltype,
            cast(testingschoolcode as int) as testingschoolcode,
            cast(colorcontrast as numeric) as colorcontrast,
            cast(elaconstructedresponse as numeric) as elaconstructedresponse,
            cast(elalconstructedresponse as numeric) as elalconstructedresponse,
            cast(
                elalselectedresponseortechnologyenhanceditems as numeric
            ) as elalselectedresponseortechnologyenhanceditems,
            cast(
                elaselectedresponseortechnologyenhanceditems as numeric
            ) as elaselectedresponseortechnologyenhanceditems,
            cast(emergencyaccommodation as numeric) as emergencyaccommodation,
            cast(
                englishlearneraccommodatedresponses as numeric
            ) as englishlearneraccommodatedresponses,
            cast(
                homelessprimarynighttimeresidence as numeric
            ) as homelessprimarynighttimeresidence,
            cast(humanreaderorhumansigner as numeric) as humanreaderorhumansigner,
            cast(localstudentidentifier as numeric) as localstudentidentifier,
            cast(
                mathematics_scienceaccommodatedresponse as numeric
            ) as mathematics_scienceaccommodatedresponse,
            cast(
                mathematicsscienceaccommodatedresponse as numeric
            ) as mathematicsscienceaccommodatedresponse,
            cast(
                multilinguallearneraccommodatedresponses as numeric
            ) as multilinguallearneraccommodatedresponses,
            cast(nottestedreason as numeric) as nottestedreason,
            cast(paperpcr1 as numeric) as paperpcr1,
            cast(paperpcr2 as numeric) as paperpcr2,
            cast(
                papersection1numberofattempteditems as numeric
            ) as papersection1numberofattempteditems,
            cast(papersection1totaltestitems as numeric) as papersection1totaltestitems,
            cast(
                papersection2numberofattempteditems as numeric
            ) as papersection2numberofattempteditems,
            cast(papersection2totaltestitems as numeric) as papersection2totaltestitems,
            cast(
                papersection3numberofattempteditems as numeric
            ) as papersection3numberofattempteditems,
            cast(papersection3totaltestitems as numeric) as papersection3totaltestitems,
            cast(
                papersection4numberofattempteditems as numeric
            ) as papersection4numberofattempteditems,
            cast(papersection4totaltestitems as numeric) as papersection4totaltestitems,
            cast(percentofitemsattempted as numeric) as percentofitemsattempted,
            cast(specialeducationplacement as numeric) as specialeducationplacement,
            cast(staffmemberidentifier as numeric) as staffmemberidentifier,
            cast(subclaim1category as numeric) as subclaim1category,
            cast(subclaim2category as numeric) as subclaim2category,
            cast(subclaim3category as numeric) as subclaim3category,
            cast(subclaim4category as numeric) as subclaim4category,
            cast(subclaim5category as numeric) as subclaim5category,
            cast(testadministrator as numeric) as testadministrator,
            cast(testcsemprobablerange as numeric) as testcsemprobablerange,
            cast(testperformancelevel as numeric) as testperformancelevel,
            cast(testreadingcsem as numeric) as testreadingcsem,
            cast(testreadingscalescore as numeric) as testreadingscalescore,
            cast(testscalescore as numeric) as testscalescore,
            cast(testscorecomplete as numeric) as testscorecomplete,
            cast(testwritingcsem as numeric) as testwritingcsem,
            cast(testwritingscalescore as numeric) as testwritingscalescore,
            cast(texttospeech as numeric) as texttospeech,
            cast(totaltestitems as numeric) as totaltestitems,
            cast(totaltestitemsattempted as numeric) as totaltestitemsattempted,
            cast(unit1numberofattempteditems as numeric) as unit1numberofattempteditems,
            cast(unit1totaltestitems as numeric) as unit1totaltestitems,
            cast(unit2numberofattempteditems as numeric) as unit2numberofattempteditems,
            cast(unit2totaltestitems as numeric) as unit2totaltestitems,
            cast(unit3numberofattempteditems as numeric) as unit3numberofattempteditems,
            cast(unit3totaltestitems as numeric) as unit3totaltestitems,
            cast(voidscorereason as numeric) as voidscorereason,

            cast(left(assessmentyear, 4) as int) as academic_year,

            cast(regexp_extract(assessmentgrade, r'Grade\s(\d+)') as int) as test_grade,

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

        from {{ source("pearson", "src_pearson__njsla_science") }}
        where summativeflag = 'Y' and testattemptednessflag = 'Y'
    )

select
    *,

    'NJSLA Science' as assessment_name,
    'Science' as discipline,

    if(testperformancelevel >= 3, true, false) as is_proficient,

    case
        testperformancelevel
        when 4
        then 'Exceeded Expectations'
        when 3
        then 'Met Expectations'
        when 2
        then 'Approached Expectations'
        when 1
        then 'Did Not Yet Meet Expectations'
    end as testperformancelevel_text,

from njsla_science
