with
    enrollments as (
        select *
        from {{ ref("base_powerschool__student_enrollments") }}  -- PowerSchool enrollment table for GL and school info
        where
            rn_year = 1
            and academic_year >= 2023
            and cohort between ({{ var("current_academic_year") }}-1) and (
                {{ var("current_academic_year") }}+5
            )
    ),

    schedules as (
        select *
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            courses_course_name like 'College and Career%'
            and rn_course_number_year = 1
            and not is_dropped_section
            and cc_academic_year >= {{ var("current_academic_year") }}
    ),

    roster as (
        select
            e._dbt_source_relation,
            -- e.academic_year,
            -- e.region,
            -- e.schoolid,
            -- e.school_name,
            e.school_abbreviation,
            e.students_dcid,
            e.student_number,
            e.state_studentnumber,
            e.lastfirst,
            -- e.first_name,
            -- e.last_name,
            e.grade_level,
            e.cohort,
            e.enroll_status,
            e.spedlep as iepstatus,
            e.is_504 as c_504_status,
            e.is_retained_year,
            e.is_retained_ever,
            e.advisor_lastfirst as advisor_name,
            s.courses_course_name as ccr_course,
            s.teacher_lastfirst as ccr_teacher,
            s.sections_external_expression as ccr_period,
        from enrollments as e
        left join
            schedules as s
            on e.academic_year = s.cc_academic_year
            and e.studentid = s.cc_studentid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
    ),

    njgpa as (
        select
            safe_cast(statestudentidentifier as string) as statestudentidentifier,
            localstudentidentifier,
            testcode as test_type,
            'State Assessment' as grad_eligible_type,
            case
                when testcode = 'ELAGP' then 'ELA' when testcode = 'MATGP' then 'Math'
            end as discipline,
            subject,
            max(testscalescore) over (
                partition by statestudentidentifier, subject
            ) as testscalescore,
            case
                when
                    max(testscalescore) over (
                        partition by statestudentidentifier, subject
                    )
                    >= 725
                then 1
                else 0
            end as met_grad_requirement
        from {{ ref("stg_pearson__njgpa") }} as c
        where testscorecomplete = 1.0 and testcode in ('ELAGP', 'MATGP')
    ),

    adb_roster as (  -- ADB to student_number crosswalk
        select * from {{ ref("int_kippadb__roster") }}
    ),

    adb_official_tests as (  -- ADB table with official ACT and SAT scores
        select
            ktc.student_number,
            test_type,
            concat(
                format_date('%b', stl.date), ' ', format_date('%g', stl.date)
            ) as administration_round,
            stl.date as test_date,
            'ACT/SAT' as grad_eligible_type,
            case
                when
                    stl.score_type
                    in ('act_reading', 'sat_reading_test_score', 'sat_ebrw')
                then 'ELA'
                when stl.score_type in ('act_math', 'sat_math_test_score', 'sat_math')
                then 'Math'
            end as discipline,
            case
                when stl.score_type in ('act_reading', 'sat_reading_test_score')
                then 'Reading'
                when stl.score_type in ('act_math', 'sat_math')
                then 'Math'
                when stl.score_type = 'sat_math_test_score'
                then 'Math Test'
                when stl.score_type = 'sat_ebrw'
                then 'EBRW'
            end as subject,
            stl.score as scale_score,
            row_number() over (
                partition by stl.contact, stl.score_type order by stl.score desc
            ) as rn_highest,  -- Sorts the table in desc order to calculate the highest score per score_type per student per subject
            case
                when stl.score_type in ('act_reading', 'act_math') and stl.score >= 17
                then 1
                when stl.score_type = 'sat_reading_test_score' and stl.score >= 23
                then 1
                when stl.score_type = 'sat_math_test_score' and stl.score >= 22
                then 1
                when stl.score_type = 'sat_math' and stl.score >= 440
                then 1
                when stl.score_type = 'sat_ebrw' and stl.score >= 450
                then 1
                else 0
            end as met_grad_requirement
        from {{ ref("int_kippadb__standardized_test_unpivot") }} as stl
        inner join adb_roster as ktc on stl.contact = ktc.contact_id
        where
            score_type in (
                'act_reading',
                'act_math',
                'sat_math_test_score',
                'sat_math',
                'sat_reading_test_score',
                'sat_ebrw'
            )
    ),

    act_sat_official as (select * from adb_official_tests where rn_highest = 1),

    alternative_grad_pathway as (
        select distinct
            r.student_number,
            r.state_studentnumber,
            'Alternative' as test_type,
            case
                when a.graduation_pathway_ela = 'N'
                then a.graduation_pathway_ela
                else null
            end as graduation_pathway_ela_portfolio,
            case
                when a.graduation_pathway_ela = 'M'
                then a.graduation_pathway_ela
                else null
            end as graduation_pathway_ela_iep,
            case
                when a.graduation_pathway_math = 'N'
                then a.graduation_pathway_math
                else null
            end as graduation_pathway_math_portfolio,
            case
                when a.graduation_pathway_math = 'M'
                then a.graduation_pathway_math
                else null
            end as graduation_pathway_math_iep
        from {{ ref("stg_powerschool__s_nj_stu_x") }} as a
        left join
            roster as r
            on a.studentsdcid = r.students_dcid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="r") }}
        where
            a.graduation_pathway_ela in ('N', 'M')
            or a.graduation_pathway_math in ('N', 'M')

    ),

    alternative_grad_pathway_long as (
        select
            student_number,
            state_studentnumber,
            test_type,
            case
                when split(alt_grad_pathway, '_')[offset(2)] = 'math'
                then 'Math'
                else 'ELA'
            end as discipline,
            case
                when split(alt_grad_pathway, '_')[offset(2)] = 'math'
                then 'Math'
                else 'ELA'
            end as subject,
            case
                when split(alt_grad_pathway, '_')[offset(3)] = 'portfolio'
                then 'Portfolio'
                else 'IEP'
            end as grad_eligible_type,
            alt_grad_code as value,
            1 as met_grad_requirement
        from
            alternative_grad_pathway unpivot (
                alt_grad_code for alt_grad_pathway in (
                    graduation_pathway_ela_portfolio,
                    graduation_pathway_math_portfolio,
                    graduation_pathway_ela_iep,
                    graduation_pathway_math_iep
                )
            ) as u
    ),

    grad_options_append_final as (
        select
            r.student_number as student_number_grad,
            r.state_studentnumber as state_studentnumber_grad,
            a.grad_eligible_type,
            a.test_type,
            a.discipline,
            a.subject,
            safe_cast(a.testscalescore as string) as value,
            a.met_grad_requirement,
            case
                when
                    sum(met_grad_requirement) over (
                        partition by r.student_number, a.discipline
                    )
                    > 0
                then 1
                else 0
            end as eligible_for_discipline
        from roster as r
        left join njgpa as a on r.state_studentnumber = a.statestudentidentifier
        where a.subject is not null
        union all
        select
            r.student_number as student_number_grad,
            r.state_studentnumber as state_studentnumber_grad,
            a.grad_eligible_type,
            a.test_type,
            a.discipline,
            a.subject,
            safe_cast(a.scale_score as string) as value,
            a.met_grad_requirement,
            case
                when
                    sum(met_grad_requirement) over (
                        partition by r.student_number, a.discipline
                    )
                    > 0
                then 1
                else 0
            end as eligible_for_discipline
        from roster as r
        left join act_sat_official as a on r.student_number = a.student_number
        where a.subject is not null
        union all
        select
            r.student_number as student_number_grad,
            r.state_studentnumber as state_studentnumber_grad,
            a.grad_eligible_type,
            a.test_type,
            a.discipline,
            a.subject,
            a.value,
            a.met_grad_requirement,
            case
                when
                    sum(met_grad_requirement) over (
                        partition by r.student_number, a.discipline
                    )
                    > 0
                then 1
                else 0
            end as eligible_for_discipline
        from roster as r
        left join
            alternative_grad_pathway_long as a on r.student_number = a.student_number
        where a.subject is not null
    ),

    roster_and_grad_options as (
        select
            * except (
                _dbt_source_relation, student_number_grad, state_studentnumber_grad
            )
        from roster as r
        left join
            grad_options_append_final as o on r.student_number = o.student_number_grad
    ),

    grad_options_final as (
        select
            student_number_grad,
            safe_cast(sum(ela) as int64) as ela,
            safe_cast(sum(math) as int64) as math,
        from
            (
                select distinct student_number as student_number_grad, ela, math
                from
                    roster_and_grad_options pivot (
                        sum(eligible_for_discipline) for discipline in ('ELA', 'Math')
                    ) as p
            )
        group by student_number_grad
    )

select * except (student_number_grad),
from roster_and_grad_options as r
left join grad_options_final as f on r.student_number = f.student_number_grad
