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
            e.discipline,
            e.powerschool_credittype,

            /* this is not their final code, but it is used to calculate their final 
            code */
            u.values_column as ps_grad_path_code,

            case
                when u.values_column in ('M', 'N')
                then true
                when u.values_column in ('O', 'P')
                then false
            end as pre_met_pathway_cutoff,

            /* needed to join on transfer njgpa scores */
            safe_cast(e.state_studentnumber as numeric) as state_studentnumber_int,

            if(e.has_fafsa = 'Yes', true, false) as has_fafsa,

            /* this is the date we start holding 11th graders accountable to 
            fulfilling the NJGPA test requirement */
            if(
                current_date('{{ var("local_timezone") }}')
                < date({{ var("current_academic_year") + 1 }}, 05, 31),
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
            s.state_studentnumber,
            s.salesforce_id,

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
            s.state_studentnumber,
            s.salesforce_id,

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

        /* act/sat scores */
        select
            s.student_number,
            s.state_studentnumber,
            s.salesforce_id,

            a.scale_score,
            a.score_type,
            a.subject_area,
            a.scope as pathway_option,

            if(a.course_discipline = 'ENG', 'ELA', 'Math') as discipline,

        from students as s
        inner join
            {{ ref("int_assessments__college_assessment") }} as a
            on s.salesforce_id = a.salesforce_id
            and s.powerschool_credittype = a.course_discipline
            and a.scope in ('ACT', 'SAT')
            and a.course_discipline in ('MATH', 'ENG')
            and a.score_type not in ('act_english', 'act_science')

        union all

        /* psat scores */
        select
            s.student_number,
            s.state_studentnumber,
            s.salesforce_id,

            p.scale_score,
            p.score_type,
            p.subject_area,
            p.scope as pathway_option,

            if(p.course_discipline = 'ENG', 'ELA', 'Math') as discipline,

        from students as s
        inner join
            {{ ref("int_assessments__college_assessment") }} as p
            on s.student_number = p.student_number
            and s.powerschool_credittype = p.course_discipline
            and p.scope in ('PSAT10', 'PSAT NMSQT')
            and p.course_discipline in ('MATH', 'ENG')
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
            s.cohort,
            s.discipline,
            s.powerschool_credittype,
            s.ps_grad_path_code,
            s.has_fafsa,
            s.njgpa_season_11th,
            s.fafsa_season_12th,

            c.type as pathway_option,
            c.subject as score_type,
            c.code as pathway_code,
            c.cutoff,

            p.scale_score,
            p.subject_area,

            if(p.scale_score >= c.cutoff, true, false) as met_pathway_cutoff,
        from students as s
        left join
            `teamster-332318`.`_grangel_reporting`.`stg_reporting__promo_status_cutoffs`
            as c
            on s.cohort = c.cohort
            and s.discipline = c.discipline
            and c.`domain` = 'Graduation Pathway'
        left join
            scores as p
            on c.type = p.pathway_option
            and c.subject = p.score_type
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

        from students as s
        where s.ps_grad_path_code in ('M', 'N', 'O', 'P')
    ),

    /* did the student ever meet the min reqs for college readiness for SAT? */
    met_sat_subject_mins as (
        select student_number, max(ela) as met_sat_ela, max(math) as met_sat_math,
        from
            lookup_table
            pivot (max(met_pathway_cutoff) for discipline in ('ELA', 'Math'))
        where score_type in ('sat_ebrw', 'sat_math')
        group by all
    ),

    /* determining if any of the scores for the score_type (if it exists)
    met the pathway option */
    unpivot_calcs as (
        select
            _dbt_source_relation,
            student_number,
            discipline,
            ps_grad_path_code,

            /* taking the njgpa at least once is a requirement to consider other 
            pathways */
            if(max(met_njgpa) is not null, true, false) as njgpa_attempt,

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
        group by all
    ),

    /* calculating if the student met the discipline overall, regardless of how they 
    did it, assuming they took the njgpa */
    met_subject as (
        select student_number, max(ela) as met_ela, max(math) as met_math,
        from
            unpivot_calcs pivot (
                max(
                    met_njgpa or met_act or met_sat or met_psat10 or met_psat_nmsqt
                ) for discipline
                in ('ELA', 'Math')
            )
        where njgpa_attempt and ps_grad_path_code is null
        group by all

        union all

        select student_number, max(ela) as met_ela, max(math) as met_math,
        from
            unpivot_calcs pivot (
                max(
                    met_njgpa or met_act or met_sat or met_psat10 or met_psat_nmsqt
                ) for discipline
                in ('ELA', 'Math')
            )
        where njgpa_attempt and ps_grad_path_code not in ('M', 'N', 'O', 'P')
        group by all

        union all

        select student_number, max(ela) as met_ela, max(math) as met_math,
        from
            unpivot_calcs
            pivot (max(met_dlm or met_portfolio) for discipline in ('ELA', 'Math'))
        where ps_grad_path_code in ('M', 'N', 'O', 'P')
        group by all
    ),

    /* calculating if the student attempted njgpa for the discipline */
    attempted_subject_njgpa as (
        select
            student_number,
            max(ela) as attempted_njgpa_ela,
            max(math) as attempted_njgpa_math,
        from unpivot_calcs pivot (max(njgpa_attempt) for discipline in ('ELA', 'Math'))
        group by all
    ),

    roster as (
        select
            l.*,

            coalesce(s.met_sat_ela) as met_sat_ela,
            coalesce(s.met_sat_math) as met_sat_math,

            coalesce(u.met_dlm, false) as met_dlm,
            coalesce(u.met_portfolio, false) as met_portfolio,
            coalesce(u.njgpa_attempt, false) as njgpa_attempt,
            coalesce(u.met_njgpa, false) as met_njgpa,
            coalesce(u.met_act, false) as met_act,
            coalesce(u.met_sat, false) as met_sat,
            coalesce(u.met_psat10, false) as met_psat10,
            coalesce(u.met_psat_nmsqt, false) as met_psat_nmsqt,

            coalesce(attempted_njgpa_ela, false) as attempted_njgpa_ela,
            coalesce(attempted_njgpa_math, false) as attempted_njgpa_math,

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
        left join met_sat_subject_mins as s on l.student_number = s.student_number
        left join attempted_subject_njgpa as n on l.student_number = n.student_number
        left join met_subject as m on l.student_number = m.student_number
    )

select
    *,

    if(met_sat_ela and met_sat_math, true, false) as met_sat_subject_mins,

    /* negative value means short; positive value means above min required */
    if(scale_score is not null, scale_score - cutoff, null) as points_short,

    case
        when grade_level != 12
        then ps_grad_path_code
        when ps_grad_path_code in ('M', 'N', 'O', 'P')
        then ps_grad_path_code
        when met_njgpa
        then 'S'
        when njgpa_attempt and not met_njgpa and met_act
        then 'E'
        when njgpa_attempt and not met_njgpa and not met_act and met_sat
        then 'D'
        when
            njgpa_attempt
            and not met_njgpa
            and not met_act
            and not met_sat
            and met_psat10
        then 'J'
        when
            njgpa_attempt
            and not met_njgpa
            and not met_act
            and not met_sat
            and not met_psat10
            and met_psat_nmsqt
        then 'K'
        else 'R'
    end as final_grad_path_code,

    case
        when grade_level <= 10
        then 'Grad Eligible'
        /* iep exempt or portfolio, non-12th grade */
        when grade_level != 12 and ps_grad_path_code in ('M', 'N')
        then 'Grad Eligible'

        /* 11th graders before njgpa */
        when grade_level = 11 and not njgpa_season_11th
        then 'Grad Eligible'
        /* 11th graders after njgpa without njgpa attempt */
        when grade_level = 11 and njgpa_season_11th and not njgpa_attempt
        then 'Not Grad Eligible. Missing NJGPA.'
        /* 11th graders who tried njgpa and passed both */
        when
            grade_level = 11
            and njgpa_season_11th
            and njgpa_attempt
            and met_ela
            and met_math
        then 'Grad Eligible'
        /* 11th graders who tried njgpa and passed only ela */
        when
            grade_level = 11
            and njgpa_season_11th
            and njgpa_attempt
            and met_ela
            and not met_math
        then 'ELA Eligible only'
        /* 11th graders who tried njgpa and passed only math */
        when
            grade_level = 11
            and njgpa_season_11th
            and njgpa_attempt
            and not met_ela
            and met_math
        then 'Math Eligible only'

        /* 12th graders regardless of fafsa season with codes O or P */
        when grade_level = 12 and ps_grad_path_code in ('O', 'P')
        then 'Not Grad Eligible'
        /* 12th graders before fafsa season with iep exempt or portfolio */
        when
            grade_level = 12
            and not fafsa_season_12th
            and ps_grad_path_code in ('M', 'N')
        then 'Grad Eligible'
        /* 12th graders after fafsa season with iep exempt or portfolio */
        when
            grade_level = 12
            and fafsa_season_12th
            and not has_fafsa
            and ps_grad_path_code in ('M', 'N')
        then 'Not Grad Eligible. Missing FAFSA.'
        /* 12th graders havent attempted njgpa */
        when grade_level = 12 and not njgpa_attempt
        then 'Not Grad Eligible. No NJGPA attempt.'

        /* 12th graders before fafsa season. took njgpa and qualified with some
        pathway */
        when
            grade_level = 12
            and not fafsa_season_12th
            and njgpa_attempt
            and met_ela
            and met_math
        then 'Grad Eligible'
        /* 12th graders before fafsa season. took njgpa and qualified with some pathway
        ela only */
        when
            grade_level = 12
            and not fafsa_season_12th
            and njgpa_attempt
            and met_ela
            and not met_math
        then 'ELA Eligible only'
        /* 12th graders before fafsa season. took njgpa and qualified with some pathway
        math only */
        when
            grade_level = 12
            and not fafsa_season_12th
            and njgpa_attempt
            and not met_ela
            and met_math
        then 'Math Eligible only'
        /* 12th graders after fafsa season. has fafsa. took njgpa but didnt qualify with any
        pathway */
        when
            grade_level = 12
            and fafsa_season_12th
            and has_fafsa
            and njgpa_attempt
            and not met_ela
            and not met_math
        then 'Not Grad Eligible. No pathway met.'
        /* 12th graders after fafsa season. no fafsa. took njgpa but didnt qualify with any
        pathway */
        when
            grade_level = 12
            and fafsa_season_12th
            and not has_fafsa
            and njgpa_attempt
            and not met_ela
            and not met_math
        then 'Not Grad Eligible. Missing FAFSA. No pathway met.'
        /* 12th grader after fafsa season, meets all requirements via some pathway */
        when
            grade_level = 12
            and fafsa_season_12th
            and has_fafsa
            and njgpa_attempt
            and met_ela
            and met_math
        then 'Grad Eligible'
        /* 12th grader after fafsa season, took NJGPA, ELA pathway met only somehow */
        when
            grade_level = 12
            and fafsa_season_12th
            and has_fafsa
            and njgpa_attempt
            and met_ela
            and not met_math
        then 'ELA Eligible Only'
        /* 12th grader after fafsa season, took NJGPA, math pathway met only somehow */
        when
            grade_level = 12
            and fafsa_season_12th
            and has_fafsa
            and njgpa_attempt
            and not met_ela
            and met_math
        then 'Math Eligible Only'
        /* 12th graders after fafsa season. took njgpa but didnt qualify with any
        pathway */
        when
            grade_level = 12
            and fafsa_season_12th
            and has_fafsa
            and njgpa_attempt
            and not met_ela
            and not met_math
        then 'Not Grad Eligible. No pathway met.'
        /* 12th graders after fafsa season. took njgpa, met pathway, but missing
        fafsa */
        when
            grade_level = 12
            and fafsa_season_12th
            and not has_fafsa
            and njgpa_attempt
            and met_ela
            and met_math
        then 'Not Grad Eligible. Missing FAFSA.'
        /* 12th graders after fafsa season. took njgpa, met ela pathway, but missing
        fafsa */
        when
            grade_level = 12
            and fafsa_season_12th
            and not has_fafsa
            and njgpa_attempt
            and met_ela
            and not met_math
        then 'ELA Eligible Only. Missing FAFSA.'
        /* 12th graders after fafsa season. took njgpa, met math pathway, but missing 
        fafsa */
        when
            grade_level = 12
            and fafsa_season_12th
            and not has_fafsa
            and njgpa_attempt
            and not met_ela
            and met_math
        then 'Math Eligible Only. Missing FAFSA.'
        when
            grade_level = 12
            and fafsa_season_12th
            and has_fafsa
            and not njgpa_attempt
            and met_ela
            and met_math
        then 'Not Grad Eligible. Has pathway, but needs NJGPA attempt.'

        else 'New category. Need new logic.'
    end as grad_eligibility,

    case
        when pathway_code = 'M'
        then 'DLM'
        when pathway_code = 'N'
        then 'Portfolio'
        when pathway_code = 'O'
        then 'Met No Requirements'
        when pathway_code = 'P'
        then 'Incomplete Credits'
        when pathway_code = 'S'
        then subject_area
        when pathway_code in ('E', 'D', 'J', 'K')
        then concat(pathway_option, ' ', subject_area)
        else 'No Data'
    end as test_type,

    row_number() over (
        partition by student_number, discipline order by pathway_option
    ) as rn_discipline_distinct,
from roster
