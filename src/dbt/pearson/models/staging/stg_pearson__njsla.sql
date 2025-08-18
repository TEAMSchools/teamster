with
    njsla as (
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
                englishlearnerel,
                federalraceethnicity,
                filler,
                gradelevelwhenassessed,
                homelessprimarynighttimeresidence,
                humanreaderorhumansigner,
                localstudentidentifier,
                mathematics_scienceaccommodatedresponse,
                mathematicsscienceaccommodatedresponse,
                multilinguallearneraccommodatedresponses,
                multilinguallearnerml,
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
                shipreportdistrictcode,
                shipreportschoolcode,
                specialeducationplacement,
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
            cast(testperformancelevel as int) as testperformancelevel,
            cast(colorcontrast as numeric) as colorcontrast,
            cast(elaconstructedresponse as numeric) as elaconstructedresponse,
            cast(elalconstructedresponse as numeric) as elalconstructedresponse,
            cast(
                elaselectedresponseortechnologyenhanceditems as numeric
            ) as elaselectedresponseortechnologyenhanceditems,
            cast(
                elalselectedresponseortechnologyenhanceditems as numeric
            ) as elalselectedresponseortechnologyenhanceditems,
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
            cast(voidscorereason as numeric) as voidscorereason,

            cast(left(assessmentyear, 4) as int) as academic_year,

            cast(regexp_extract(assessmentgrade, r'Grade\s(\d+)') as int) as test_grade,

            coalesce(multilinguallearnerml, englishlearnerel) as englishlearnerel,

            if(
                `subject`
                in ('English Language Arts', 'English Language Arts/Literacy'),
                'ELA',
                'Math'
            ) as discipline,

        from {{ source("pearson", "src_pearson__njsla") }}
        where summativeflag = 'Y' and testattemptednessflag = 'Y'
    )

select
    *,

    'NJSLA' as assessment_name,

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

from njsla
