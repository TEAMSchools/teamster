-- purpose of this view: some version of the nonsense below is repeated via CTEs in
-- two views: the old version of this view (int_students__graduation_path_codes.sql) and
-- rpt_tableau__graduation_requirements.sql. path_codes then feeds autocomm_students
-- to send to PS the final graduation eligibility code. currently, the CTE versions
-- require manual adjustments of the ACT SAT PSAT et al thresholds needed to
-- calculate eligibility for graduation under these pathways IF a student tests for
-- NJGPA. i can share a doc of the logic behind the checks, if that helps. the point
-- is that these grad requirements can change even after a student has already been
-- assigned a path, so we need to be able to check grad pathways at the academic year
-- level (i.e. a student who is supposed to graduate this year may have different
-- ACT/SAT/PSAT thredsholds than a student who is supposed to graduate next year). i
-- started building a lookup table that allows me to customize the thresholds by
-- cohort/test/score_type (subject). it currently lives on the same table where walters
-- has the promo status cutoffs (stg_reporting__promo_status_cutoffs). im not married
-- to this location, so if you think it goes better somewhere else, please move it.
-- this view will also help us track the distribution of grad pathways over time to
-- share with katie and co which pathways our students take the most, which can
-- influence strategy decisions around which college readiness assessments serve our
-- students best. thank you for coming to my tedtalk
with
    students as (
        select
            e._dbt_source_relation,
            e.students_dcid,
            e.studentid,
            e.student_number,
            e.state_studentnumber,
            e.salesforce_id,
            e.grade_level,
            e.cohort,
            e.has_fafsa,
            e.discipline,

            -- this is not their final code, but it is used to calculate their final
            -- code
            u.values_column as ps_grad_path_code,

            safe_cast(e.state_studentnumber as numeric) as state_studentnumber_int,

            -- this is the date we start holding 11th graders accountable to
            -- fulfilling the NJGPA test requirement
            date({{ var("current_academic_year") + 1 }}, 05, 31) as njgpa_date_11th,

            -- this is the date we start holding 12th graders accountable to
            -- fulfilling the FAFSA requirement
            if(
                current_date('{{ var("local_timezone") }}')
                < date({{ var("current_academic_year") + 1 }}, 01, 01),
                true,
                false
            ) as is_before_fafsa_12th,

        from {{ ref("int_extracts__student_enrollments_subjects") }} as e
        left join
            {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as u
            on e.students_dcid = u.studentsdcid
            and e.discipline = u.discipline
            and {{ union_dataset_join_clause(left_alias="e", right_alias="u") }}
            and u.value_type = 'Graduation Pathway'
        where e.region != 'Miami' and grade_level >= 8 and rn_undergrad = 1
    ),

    scores as (
        select
            s.student_number,
            s.state_studentnumber,
            s.salesforce_id,
            x.testscalescore,

            x.discipline,

        from students as s
        inner join
            {{ ref("int_powerschool__state_assessments_transfer_scores") }} as x
            on s.state_studentnumber = x.state_studentnumber

        union all

        select
            s.student_number,
            s.state_studentnumber,
            s.salesforce_id,
            n.testscalescore,

            if(n.testcode = 'ELAGP', 'ELA', 'Math') as discipline,

        from students as s
        inner join
            {{ ref("stg_pearson__njgpa") }} as n
            on s.state_studentnumber_int = n.statestudentidentifier
        where n.testscorecomplete = 1 and n.testcode in ('ELAGP', 'MATGP')
    )
/*
    njgpa_rollup as (
        select state_studentnumber, discipline, max(testscalescore) as testscalescore,
        from njgpa
        group by state_studentnumber, discipline
    )

    act_sat_psat_official as (
        select s.state_studentnumber,
        from students as s
        inner join
            {{ ref("int_assessments__college_assessment") }} as a
            on s.salesforce_id = a.salesforce_id

        union all

        select *
        from students as s
        inner join
            {{ ref("int_assessments__college_assessment") }} as a
            on s.student_number = a.student_number
    )*/
select *
from scores
