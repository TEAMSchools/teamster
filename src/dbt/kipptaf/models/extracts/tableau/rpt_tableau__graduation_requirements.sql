with
    roster as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.academic_year_display,
            e.region,
            e.schoolid,
            e.school_name,
            e.school,
            e.students_dcid,
            e.studentid,
            e.student_number,
            e.student_name,
            e.student_first_name,
            e.student_last_name,
            e.grade_level,
            e.enroll_status,
            e.cohort,
            e.advisory,
            e.iep_status,
            e.is_504,
            e.lep_status,
            e.is_retained_year,
            e.is_retained_ever,
            e.student_email as student_email_google,
            e.salesforce_id as kippadb_contact_id,
            e.ktc_cohort,
            e.has_fafsa,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,
            s.sections_section_number as section_number,

            discipline,

            safe_cast(e.state_studentnumber as int) as state_studentnumber,

        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.studentid = s.cc_studentid
            and e.academic_year = s.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
            and s.courses_course_name like 'College and Career%'
            and s.rn_course_number_year = 1
            and not s.is_dropped_section
        cross join unnest(['Math', 'ELA']) as discipline
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.schoolid != 999999
            and e.cohort between ({{ var("current_academic_year") - 1 }}) and (
                {{ var("current_academic_year") + 5 }}
            )
    ),

    transfer_scores as (
        select
            b._dbt_source_relation,
            b.name as test_name,

            s.studentid,
            s.grade_level as assessment_grade_level,

            t.numscore as testscalescore,
            t.alphascore as testperformancelevel,

            r.name as testcode,

            case
                r.name when 'ELAGP' then 'ELA' when 'MATGP' then 'Math'
            end as discipline,
            case
                r.name
                when 'ELAGP'
                then 'English Language Arts'
                when 'MATGP'
                then 'Mathematics'
            end as `subject`,
        from {{ ref("stg_powerschool__test") }} as b
        left join
            {{ ref("stg_powerschool__studenttest") }} as s
            on b.id = s.testid
            and {{ union_dataset_join_clause(left_alias="b", right_alias="s") }}
        left join
            {{ ref("stg_powerschool__studenttestscore") }} as t
            on s.studentid = t.studentid
            and s.id = t.studenttestid
            and {{ union_dataset_join_clause(left_alias="s", right_alias="t") }}
        left join
            {{ ref("stg_powerschool__testscore") }} as r
            on s.testid = r.testid
            and t.testscoreid = r.id
            and {{ union_dataset_join_clause(left_alias="s", right_alias="r") }}
        where b.name = 'NJGPA'
    ),

    transfer_roster as (
        select
            e.student_number as localstudentidentifier,

            x.subject,
            x.testcode,
            x.testscalescore,
            x.discipline,

            safe_cast(e.state_studentnumber as int) as statestudentidentifier,
        from roster as e
        left join
            transfer_scores as x
            on e.studentid = x.studentid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="x") }}
        where x.studentid is not null
    ),

    njgpa as (
        select
            localstudentidentifier,
            statestudentidentifier,
            `subject`,
            testcode,
            testscalescore,

            case
                when testcode = 'ELAGP' then 'ELA' when testcode = 'MATGP' then 'Math'
            end as discipline,
        from {{ ref("stg_pearson__njgpa") }}
        where testscorecomplete = 1 and testcode in ('ELAGP', 'MATGP')

        union all

        select
            localstudentidentifier,
            statestudentidentifier,
            `subject`,
            testcode,
            testscalescore,
            discipline,
        from transfer_roster
    ),

    njgpa_rollup as (
        select
            localstudentidentifier,
            statestudentidentifier,
            testcode,
            `subject`,
            discipline,

            max(testscalescore) as testscalescore,
        from njgpa
        group by
            localstudentidentifier,
            statestudentidentifier,
            testcode,
            `subject`,
            discipline
    ),

    act_sat_psat_official as (
        select
            contact,
            test_type,
            score,

            case
                when score_type in ('act_reading', 'sat_reading_test_score', 'sat_ebrw')
                then 'ELA'
                when score_type in ('act_math', 'sat_math_test_score', 'sat_math')
                then 'Math'
            end as discipline,

            case
                when score_type in ('act_reading', 'sat_reading_test_score')
                then 'Reading'
                when score_type in ('act_math', 'sat_math')
                then 'Math'
                when score_type = 'sat_math_test_score'
                then 'Math Test'
                when score_type = 'sat_ebrw'
                then 'EBRW'
            end as `subject`,

            case
                when score_type in ('act_reading', 'act_math') and score >= 17
                then true
                when score_type = 'sat_reading_test_score' and score >= 23
                then true
                when score_type = 'sat_math_test_score' and score >= 22
                then true
                when score_type = 'sat_math' and score >= 440
                then true
                when score_type = 'sat_ebrw' and score >= 450
                then true
                else false
            end as met_pathway_requirement,
        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where
            rn_highest = 1
            and score_type in (
                'act_reading',
                'act_math',
                'sat_math_test_score',
                'sat_math',
                'sat_reading_test_score',
                'sat_ebrw'
            )

        union all

        select
            cast(local_student_id as string) as contact,

            'PSAT' as test_type,

            score,

            if(
                score_type
                in ('psat_eb_read_write_section_score', 'psat_reading_test_score'),
                'ELA',
                'Math'
            ) as discipline,

            case
                when score_type = 'psat_reading_test_score'
                then 'Reading'
                when score_type = 'psat_math_section_score'
                then 'Math'
                when score_type = 'psat_math_test_score'
                then 'Math Test'
                when score_type = 'psat_eb_read_write_section_score'
                then 'EBRW'
            end as `subject`,

            case
                when
                    score_type in ('psat_reading_test_score', 'psat_math_test_score')
                    and score >= 21
                then true
                when
                    score_type
                    in ('psat_math_section_score', 'psat_eb_read_write_section_score')
                    and score >= 420
                then true
                else false
            end as met_pathway_requirement,
        from {{ ref("int_illuminate__psat_unpivot") }}
        where
            rn_highest = 1
            and score_type in (
                'psat_eb_read_write_section_score',
                'psat_math_test_score',
                'psat_math_section_score',
                'psat_reading_test_score'
            )
            and test_name != 'PSAT89'
    ),

    grad_options_append_final as (
        select
            r.student_number,

            a.discipline,
            a.subject,
            a.testcode as test_type,

            'State Assessment' as pathway_option,

            cast(a.testscalescore as string) as `value`,

            if(a.testscalescore >= 725, true, false) as met_pathway_requirement,
        from roster as r
        inner join njgpa_rollup as a on r.state_studentnumber = a.statestudentidentifier

        union all

        select
            r.student_number,

            a.discipline,
            a.subject,
            a.test_type,

            'ACT/SAT' as pathway_option,

            cast(a.score as string) as `value`,

            a.met_pathway_requirement,
        from roster as r
        inner join act_sat_psat_official as a on r.kippadb_contact_id = a.contact
        where a.test_type in ('ACT', 'SAT')

        union all

        select
            r.student_number,

            a.discipline,
            a.subject,
            a.test_type,

            'PSAT' as pathway_option,

            cast(a.score as string) as `value`,

            a.met_pathway_requirement,
        from roster as r
        inner join
            act_sat_psat_official as a on cast(r.student_number as string) = a.contact
        where a.test_type = 'PSAT'

        union all

        select
            r.student_number,

            a.discipline,
            a.discipline as `subject`,

            case
                when a.is_iep_eligible
                then 'IEP'
                when a.is_portfolio_eligible
                then 'Portfolio'
            end as test_type,

            'Alternative' as pathway_option,

            a.values_column as `value`,
            a.met_requirement as met_pathway_requirement,
        from roster as r
        inner join
            {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as a
            on r.students_dcid = a.studentsdcid
            and {{ union_dataset_join_clause(left_alias="r", right_alias="a") }}
            and a.value_type = 'Graduation Pathway'
            and a.values_column in ('M', 'N')
    )

select distinct
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.schoolid,
    r.school_name,
    r.school,
    r.student_number,
    r.state_studentnumber,
    r.kippadb_contact_id,
    r.students_dcid,
    r.student_name,
    r.student_first_name,
    r.student_last_name,
    r.enroll_status,
    r.cohort,
    r.ktc_cohort,
    r.has_fafsa,
    r.grade_level,
    r.iep_status,
    r.is_504,
    r.lep_status,
    r.is_retained_year,
    r.is_retained_ever,
    r.student_email_google,
    r.advisory,
    r.courses_course_name as ccr_course,
    r.teacher_lastfirst as ccr_teacher,
    r.sections_external_expression as ccr_period,
    r.section_number as ccr_section_number,
    r.discipline,

    g.pathway_option,
    g.test_type,
    g.subject,
    g.value,
    g.met_pathway_requirement,

    c.code,
    c.njgpa_attempt,
    c.njgpa_pass,
    c.act,
    c.sat,
    c.psat,
    c.final_grad_path,
from roster as r
left join
    grad_options_append_final as g
    on r.student_number = g.student_number
    and r.discipline = g.discipline
left join
    {{ ref("int_students__graduation_path_codes") }} as c
    on r.student_number = c.student_number
    and r.discipline = c.discipline
