with
    parcc as (
        select
            * except (
                accountabledistrictcode,
                accountableorganizationaltype,
                accountableschoolcode,
                colorcontrast,
                elaconstructedresponse,
                elalconstructedresponse,
                elalselectedresponseortechnologyenhanceditems,
                elaselectedresponseortechnologyenhanceditems,
                emergencyaccommodation,
                englishlearneraccommodatedresponses,
                federalraceethnicity,
                filler,
                gradelevelwhenassessed,
                humanreaderorhumansigner,
                localstudentidentifier,
                mathematicsresponse,
                mathematicsresponseel,
                mathematicsscienceaccommodatedresponse,
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
                responsibleaccountabledistrictcode,
                responsibleaccountableschoolcode,
                responsibledistrictcode,
                responsibleorganizationaltype,
                responsibleorganizationcodetype,
                responsibleschoolcode,
                shipreportdistrictcode,
                shipreportschoolcode,
                specialeducationplacement,
                statefield7,
                statefield8,
                statestudentidentifier,
                subclaim1category,
                subclaim2category,
                subclaim3category,
                subclaim4category,
                subclaim5category,
                testcsemprobablerange,
                testingdistrictcode,
                testingorganizationaltype,
                testingschoolcode,
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
                unit4numberofattempteditems,
                unit4totaltestitems,
                voidscorereason
            ),

            cast(accountabledistrictcode as int) as accountabledistrictcode,
            cast(accountableorganizationaltype as int) as accountableorganizationaltype,
            cast(accountableschoolcode as int) as accountableschoolcode,
            cast(federalraceethnicity as int) as federalraceethnicity,
            cast(gradelevelwhenassessed as int) as gradelevelwhenassessed,
            cast(
                responsibleaccountabledistrictcode as int
            ) as responsibleaccountabledistrictcode,
            cast(
                responsibleaccountableschoolcode as int
            ) as responsibleaccountableschoolcode,
            cast(responsibledistrictcode as int) as responsibledistrictcode,
            cast(responsibleorganizationaltype as int) as responsibleorganizationaltype,
            cast(
                responsibleorganizationcodetype as int
            ) as responsibleorganizationcodetype,
            cast(responsibleschoolcode as int) as responsibleschoolcode,
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
            cast(humanreaderorhumansigner as numeric) as humanreaderorhumansigner,
            cast(localstudentidentifier as numeric) as localstudentidentifier,
            cast(mathematicsresponse as numeric) as mathematicsresponse,
            cast(mathematicsresponseel as numeric) as mathematicsresponseel,
            cast(
                mathematicsscienceaccommodatedresponse as numeric
            ) as mathematicsscienceaccommodatedresponse,
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
            cast(specialeducationplacement as numeric) as specialeducationplacement,
            cast(statefield7 as numeric) as statefield7,
            cast(statefield8 as numeric) as statefield8,
            cast(subclaim1category as numeric) as subclaim1category,
            cast(subclaim2category as numeric) as subclaim2category,
            cast(subclaim3category as numeric) as subclaim3category,
            cast(subclaim4category as numeric) as subclaim4category,
            cast(subclaim5category as numeric) as subclaim5category,
            cast(testcsemprobablerange as numeric) as testcsemprobablerange,
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
            cast(unit4numberofattempteditems as numeric) as unit4numberofattempteditems,
            cast(unit4totaltestitems as numeric) as unit4totaltestitems,
            cast(voidscorereason as numeric) as voidscorereason,

            cast(
                cast(shipreportdistrictcode as numeric) as int
            ) as shipreportdistrictcode,
            cast(cast(shipreportschoolcode as numeric) as int) as shipreportschoolcode,
            cast(cast(testperformancelevel as numeric) as int) as testperformancelevel,

            cast(left(assessmentyear, 4) as int) as academic_year,

            cast(regexp_extract(assessmentgrade, r'Grade\s(\d+)') as int) as test_grade,

            if(
                `subject` = 'English Language Arts/Literacy', 'ELA', 'Math'
            ) as discipline,

        from {{ source("pearson", "src_pearson__parcc") }}
        where summativeflag = 'Y' and testattemptednessflag = 'Y'
    )

select
    *,

    'PARCC' as assessment_name,

    if(testperformancelevel >= 4, true, false) as is_proficient,
    if(testperformancelevel <= 2, true, false) as is_bl_fb,

    case
        testperformancelevel
        when 5
        then 'Exceeded Expectations'
        when 4
        then 'Met Expectations'
        when 3
        then 'Approached Expectations'
        when 2
        then 'Partially Met Expectations'
        when 1
        then 'Did Not Yet Meet Expectations'
    end as testperformancelevel_text,

from parcc
