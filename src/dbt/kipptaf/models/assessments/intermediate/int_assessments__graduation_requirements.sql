with
    student_id_crosswalk as (
        select distinct
            e._dbt_source_relation,
            e.studentid,
            e.students_dcid,
            e.student_number,
            e.state_studentnumber,
            e.fleid,
            adb.contact_id
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("int_kippadb__roster") }} as adb
            on e.student_number = adb.student_number
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.cohort between ({{ var("current_academic_year") }}-1) and (
                {{ var("current_academic_year") }}+5
            )
            and e.schoolid <> 999999
    ),

    njgpa as (
        select
            safe_cast(statestudentidentifier as string) as state_studentnumber,
            localstudentidentifier as student_number,
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
            end as met_pathway_requirement
        from {{ ref("stg_pearson__njgpa") }} as c
        where testscorecomplete = 1.0 and testcode in ('ELAGP', 'MATGP')
    ),

    njgpa_attempt_check as (
        select
            student_number as student_number_check,
            discipline as discipline_check,
            1 as met_njgpa_attempt_requirement,
        from njgpa
        where subject is not null
    ),

    adb_official_tests as (  -- ADB table with official ACT and SAT scores
        select
            adb.contact as adb_id,
            s.student_number,
            s.state_studentnumber,
            adb.test_type,
            concat(
                format_date('%b', adb.date), ' ', format_date('%g', adb.date)
            ) as administration_round,
            adb.date as test_date,
            'ACT/SAT' as grad_eligible_type,
            case
                when
                    adb.score_type
                    in ('act_reading', 'sat_reading_test_score', 'sat_ebrw')
                then 'ELA'
                when adb.score_type in ('act_math', 'sat_math_test_score', 'sat_math')
                then 'Math'
            end as discipline,
            case
                when adb.score_type in ('act_reading', 'sat_reading_test_score')
                then 'Reading'
                when adb.score_type in ('act_math', 'sat_math')
                then 'Math'
                when adb.score_type = 'sat_math_test_score'
                then 'Math Test'
                when adb.score_type = 'sat_ebrw'
                then 'EBRW'
            end as subject,
            adb.score as scale_score,
            row_number() over (
                partition by adb.contact, adb.score_type order by score desc
            ) as rn_highest,  -- Sorts the table in desc order to calculate the highest score per score_type per student per subject
            case
                when adb.score_type in ('act_reading', 'act_math') and adb.score >= 17
                then 1
                when adb.score_type = 'sat_reading_test_score' and adb.score >= 23
                then 1
                when adb.score_type = 'sat_math_test_score' and adb.score >= 22
                then 1
                when adb.score_type = 'sat_math' and adb.score >= 440
                then 1
                when adb.score_type = 'sat_ebrw' and adb.score >= 450
                then 1
                else 0
            end as met_pathway_requirement
        from {{ ref("int_kippadb__standardized_test_unpivot") }} as adb
        left join student_id_crosswalk as s on adb.contact = s.contact_id
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
            s.student_number,
            s.state_studentnumber,
            'Alternative' as test_type,
            case
                when p.graduation_pathway_ela = 'N'
                then graduation_pathway_ela
                else null
            end as graduation_pathway_ela_portfolio,
            case
                when p.graduation_pathway_ela = 'M'
                then graduation_pathway_ela
                else null
            end as graduation_pathway_ela_iep,
            case
                when p.graduation_pathway_math = 'N'
                then graduation_pathway_math
                else null
            end as graduation_pathway_math_portfolio,
            case
                when p.graduation_pathway_math = 'M'
                then graduation_pathway_math
                else null
            end as graduation_pathway_math_iep
        from {{ ref("stg_powerschool__s_nj_stu_x") }} as p
        left join
            student_id_crosswalk as s
            on p.studentsdcid = s.students_dcid
            and {{ union_dataset_join_clause(left_alias="p", right_alias="s") }}
        where
            p.graduation_pathway_ela in ('N', 'M')
            or p.graduation_pathway_math in ('N', 'M')
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
            1 as met_pathway_requirement
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
            a.met_pathway_requirement,
        from student_id_crosswalk as r
        left join njgpa as a on r.state_studentnumber = a.state_studentnumber
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
            a.met_pathway_requirement,
        from student_id_crosswalk as r
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
            a.met_pathway_requirement
        from student_id_crosswalk as r
        left join
            alternative_grad_pathway_long as a on r.student_number = a.student_number
        where a.subject is not null
    )

select
    * except (student_number_check, discipline_check),
    case
        when
            sum(g.met_pathway_requirement) over (
                partition by g.student_number_grad, g.discipline
            )
            > 0
            and c.met_njgpa_attempt_requirement = 1
        then 1
        else 0
    end as eligible_for_discipline
from grad_options_append_final as g
left join
    njgpa_attempt_check as c
    on g.student_number_grad = c.student_number_check
    and g.discipline = c.discipline_check
order by g.student_number_grad, g.discipline