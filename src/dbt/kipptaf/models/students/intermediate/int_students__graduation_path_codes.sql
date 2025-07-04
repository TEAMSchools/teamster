{{- config(materialized="table") -}}

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
            e.enroll_status,
            e.cohort,
            e.discipline,
            e.powerschool_credittype,
            e.met_fafsa_requirement as has_fafsa,

            /* this is not their final code, but it is used to calculate their final 
            code */
            u.values_column as ps_grad_path_code,

            /* needed to join on transfer njgpa scores */
            safe_cast(e.state_studentnumber as int) as state_studentnumber_int,

            /* this is the date we start holding 11th graders accountable to 
            fulfilling the NJGPA test requirement */
            if(
                current_date('{{ var("local_timezone") }}')
                < date({{ var("current_academic_year") + 1 }}, 06, 05),
                false,
                true
            ) as njgpa_season_11th,

            /* this is the date we start holding 12th graders accountable to fulfilling
            the FAFSA requirement */
            if(
                current_date('{{ var("local_timezone") }}')
                < date({{ var("current_academic_year") + 1 }}, 01, 01),
                false,
                true
            ) as fafsa_season_12th,

            case
                when u.values_column in ('M', 'N')
                then true
                when u.values_column in ('O', 'P')
                then false
            end as pre_met_pathway_cutoff,

            if(u.values_column = 'M', true, false) as pre_attempted_njgpa_subject,

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
        /* njgpa transfer scores */
        select
            s.student_number,

            x.testscalescore as scale_score,
            x.testcode as score_type,
            x.testcode as subject_area,
            x.test_name as pathway_option,
            x.discipline,

        from students as s
        inner join
            {{ ref("int_powerschool__state_assessments_transfer_scores") }} as x
            on s.studentid = x.studentid
            and s.discipline = x.discipline

        union all

        /* njgpa scores from file */
        select
            s.student_number,

            n.testscalescore as scale_score,
            n.testcode as score_type,
            n.testcode as subject_area,
            n.assessment_name as pathway_option,
            n.discipline,

        from students as s
        inner join
            {{ ref("stg_pearson__njgpa") }} as n
            on s.state_studentnumber_int = n.statestudentidentifier
            and s.discipline = n.discipline
        where n.testscorecomplete = 1 and n.testcode in ('ELAGP', 'MATGP')

        union all

        /* act/sat/psat scores */
        select
            student_number,
            scale_score,
            score_type,
            subject_area,
            scope as pathway_option,

            if(course_discipline = 'ENG', 'ELA', 'Math') as discipline,
        from {{ ref("int_assessments__college_assessment") }}
        where
            scope in ('ACT', 'SAT', 'PSAT10', 'PSAT NMSQT')
            and course_discipline in ('MATH', 'ENG')
            and score_type != 'act_english'
    ),

    attempted_subject_njgpa as (
        /* calculating if the student attempted njgpa for the discipline */
        select
            student_number,

            max(ela) as attempted_njgpa_ela,
            max(math) as attempted_njgpa_math,
        from scores pivot (max(score_type) for discipline in ('ELA', 'Math'))
        where pathway_option = 'NJGPA'
        group by student_number
    ),

    lookup_table as (
        select
            s._dbt_source_relation,
            s.students_dcid,
            s.studentid,
            s.student_number,
            s.state_studentnumber,
            s.salesforce_id,
            s.grade_level,
            s.enroll_status,
            s.cohort,
            s.discipline,
            s.powerschool_credittype,
            s.ps_grad_path_code,
            s.has_fafsa,
            s.njgpa_season_11th,
            s.fafsa_season_12th,

            c.pathway_option,
            c.score_type,
            c.pathway_code,
            c.cutoff,

            p.scale_score,
            p.subject_area,

            if(p.scale_score >= c.cutoff, true, false) as met_pathway_cutoff,

            if(nj.attempted_njgpa_ela is not null, true, false) as attempted_njgpa_ela,

            if(
                nj.attempted_njgpa_math is not null, true, false
            ) as attempted_njgpa_math,

        from students as s
        left join attempted_subject_njgpa as nj on s.student_number = nj.student_number
        left join
            {{ ref("stg_google_sheets__student_graduation_path_cutoffs") }} as c
            on s.cohort = c.cohort
            and s.discipline = c.discipline
        left join
            scores as p
            on c.pathway_option = p.pathway_option
            and c.score_type = p.score_type
            and s.student_number = p.student_number
        where
            s.ps_grad_path_code is null
            or s.ps_grad_path_code not in ('M', 'N', 'O', 'P')

        union all

        select
            s._dbt_source_relation,
            s.students_dcid,
            s.studentid,
            s.student_number,
            s.state_studentnumber,
            s.salesforce_id,
            s.grade_level,
            s.enroll_status,
            s.cohort,
            s.discipline,
            s.powerschool_credittype,
            s.ps_grad_path_code,
            s.has_fafsa,
            s.njgpa_season_11th,
            s.fafsa_season_12th,

            case
                s.ps_grad_path_code
                when 'M'
                then 'DLM'
                when 'N'
                then 'Portfolio'
                when 'O'
                then 'No Pathway'
                when 'P'
                then 'Incomplete Credits'
            end as pathway_option,

            case
                concat(s.discipline, s.ps_grad_path_code)
                when 'MathM'
                then 'dlm_math'
                when 'ELAM'
                then 'dlm_ela'
                when 'MathN'
                then 'portfolio_math'
                when 'ELAN'
                then 'portfolio_ela'
                when 'MathO'
                then 'no_pathway_math'
                when 'ELAO'
                then 'no_pathway_ela'
                when 'MathP'
                then 'incomplete_credits_math'
                when 'ELAP'
                then 'incomplete_credits_ela'
            end as score_type,

            s.ps_grad_path_code as pathway_code,

            0 as cutoff,
            0 as scale_score,
            s.discipline as subject_area,

            s.pre_met_pathway_cutoff as met_pathway_cutoff,

            case
                when s.ps_grad_path_code = 'M'
                then s.pre_attempted_njgpa_subject
                when nj.attempted_njgpa_ela is not null
                then true
            end as attempted_njgpa_ela,

            case
                when s.ps_grad_path_code = 'M'
                then s.pre_attempted_njgpa_subject
                when nj.attempted_njgpa_math is not null
                then true
            end as attempted_njgpa_math,

        from students as s
        left join attempted_subject_njgpa as nj on s.student_number = nj.student_number
        where s.ps_grad_path_code in ('M', 'N', 'O', 'P')
    ),

    unpivot_calcs as (
        /* determining if any of the scores for the score_type (if it exists) met the 
        pathway option */
        select
            _dbt_source_relation,
            student_number,
            discipline,

            attempted_njgpa_ela,
            attempted_njgpa_math,

            /* taking the njgpa at least once is a requirement to consider other 
            pathways */
            case
                when discipline = 'ELA' and attempted_njgpa_ela
                then true
                when discipline = 'Math' and attempted_njgpa_math
                then true
                else false
            end as njgpa_attempt,

            /* collapse the unpivot */
            max(met_dlm) as met_dlm,
            max(met_portfolio) as met_portfolio,
            max(met_njgpa) as met_njgpa,
            max(met_act) as met_act,
            max(met_sat) as met_sat,
            max(met_psat10) as met_psat10,
            max(met_psat_nmsqt) as met_psat_nmsqt,

        from
            lookup_table pivot (
                max(met_pathway_cutoff)
                for pathway_option in (
                    'DLM' as met_dlm,
                    'Portfolio' as met_portfolio,
                    'NJGPA' as met_njgpa,
                    'ACT' as met_act,
                    'SAT' as met_sat,
                    'PSAT10' as met_psat10,
                    'PSAT NMSQT' as met_psat_nmsqt
                )
            )
        where scale_score is not null
        group by
            _dbt_source_relation,
            student_number,
            discipline,
            attempted_njgpa_ela,
            attempted_njgpa_math
    ),

    unpivot_calcs_ps_code as (
        /* need the ps_grad_path_code to not lose null/null students */
        select u.*, s.ps_grad_path_code
        from unpivot_calcs as u
        inner join
            students as s
            on u.student_number = s.student_number
            and u.discipline = s.discipline
    ),

    met_subject as (
        /* calculating if the student met the discipline overall, regardless of how 
        they  did it, assuming they took the njgpa */
        select student_number, max(ela) as met_ela, max(math) as met_math,
        from
            unpivot_calcs_ps_code pivot (
                max(
                    met_dlm
                    or met_portfolio
                    or met_njgpa
                    or met_act
                    or met_sat
                    or met_psat10
                    or met_psat_nmsqt
                ) for discipline
                in ('ELA', 'Math')
            )
        where njgpa_attempt and ps_grad_path_code is null
        group by student_number

        union all

        select student_number, max(ela) as met_ela, max(math) as met_math,
        from
            unpivot_calcs_ps_code pivot (
                max(
                    met_dlm
                    or met_portfolio
                    or met_njgpa
                    or met_act
                    or met_sat
                    or met_psat10
                    or met_psat_nmsqt
                ) for discipline
                in ('ELA', 'Math')
            )
        where
            njgpa_attempt and ps_grad_path_code is not null and ps_grad_path_code != 'M'
        group by student_number

        union all

        select student_number, max(ela) as met_ela, max(math) as met_math,
        from
            unpivot_calcs_ps_code pivot (max(met_dlm) for discipline in ('ELA', 'Math'))
        where ps_grad_path_code = 'M'
        group by student_number
    ),

    roster as (
        select
            l._dbt_source_relation,
            l.students_dcid,
            l.studentid,
            l.student_number,
            l.state_studentnumber,
            l.salesforce_id,
            l.grade_level,
            l.enroll_status,
            l.cohort,
            l.discipline,
            l.powerschool_credittype,
            l.ps_grad_path_code,
            l.has_fafsa,
            l.njgpa_season_11th,
            l.fafsa_season_12th,
            l.pathway_option,
            l.score_type,
            l.pathway_code,
            l.cutoff,
            l.scale_score,
            l.subject_area,
            l.met_pathway_cutoff,

            coalesce(l.attempted_njgpa_ela, false) as attempted_njgpa_ela,
            coalesce(l.attempted_njgpa_math, false) as attempted_njgpa_math,

            coalesce(u.met_dlm, false) as met_dlm,
            coalesce(u.met_portfolio, false) as met_portfolio,
            coalesce(u.njgpa_attempt, false) as njgpa_attempt,
            coalesce(u.met_njgpa, false) as met_njgpa,
            coalesce(u.met_act, false) as met_act,
            coalesce(u.met_sat, false) as met_sat,
            coalesce(u.met_psat10, false) as met_psat10,
            coalesce(u.met_psat_nmsqt, false) as met_psat_nmsqt,

            coalesce(m.met_ela, false) as met_ela,
            coalesce(m.met_math, false) as met_math,

            row_number() over (
                partition by l.student_number, l.score_type order by l.scale_score desc
            ) as rn_highest,
        from lookup_table as l
        left join
            unpivot_calcs as u
            on l.student_number = u.student_number
            and l.discipline = u.discipline
        left join attempted_subject_njgpa as n on l.student_number = n.student_number
        left join met_subject as m on l.student_number = m.student_number
    )

select
    r.*,

    /* negative value means short; positive value means above min required */
    if(r.scale_score is not null, r.scale_score - r.cutoff, null) as points_short,

    case
        when r.pathway_code in ('M', 'N', 'O', 'P')
        then r.pathway_option
        when r.pathway_code = 'S'
        then r.subject_area
        when r.pathway_code in ('E', 'D', 'J', 'K')
        then concat(r.pathway_option, ' ', r.subject_area)
        else 'No Data'
    end as test_type,

    case
        when r.grade_level <= 10
        then r.ps_grad_path_code
        when r.ps_grad_path_code in ('M', 'N', 'O', 'P')
        then r.ps_grad_path_code
        when r.met_njgpa
        then 'S'
        when r.njgpa_attempt and not r.met_njgpa and r.met_act
        then 'E'
        when r.njgpa_attempt and not r.met_njgpa and not r.met_act and r.met_sat
        then 'D'
        when
            r.njgpa_attempt
            and not r.met_njgpa
            and not r.met_act
            and not r.met_sat
            and r.met_psat10
        then 'J'
        when
            r.njgpa_attempt
            and not r.met_njgpa
            and not r.met_act
            and not r.met_sat
            and not r.met_psat10
            and r.met_psat_nmsqt
        then 'K'
        else 'R'
    end as final_grad_path_code,

    coalesce(
        case
            when r.grade_level <= 10
            then 'Grad Eligible'
            when r.grade_level >= 11
            then g.grad_eligibility
        end,
        'New category. Need new logic.'
    ) as grad_eligibility,

    row_number() over (
        partition by r.student_number, r.discipline order by r.pathway_option
    ) as rn_discipline_distinct,

from roster as r
left join
    {{ ref("stg_google_sheets__student_graduation_path_combos") }} as g
    on r.grade_level = g.grade_level
    and r.has_fafsa = g.has_fafsa
    and r.njgpa_season_11th = g.njgpa_season_11th
    and r.fafsa_season_12th = g.fafsa_season_12th
    and r.attempted_njgpa_ela = g.attempted_njgpa_ela
    and r.attempted_njgpa_math = g.attempted_njgpa_math
    and r.met_ela = g.met_ela
    and r.met_math = g.met_math
where r.enroll_status = 0
