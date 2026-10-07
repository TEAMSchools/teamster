with
    calcs as (
        /* one row per student per discipline. A pathway is met when any score
           for it cleared its cut score. */
        select
            _dbt_source_project,
            student_number,
            discipline,
            ps_grad_path_code,
            attempted_njgpa_ela,
            attempted_njgpa_math,

            max(if(pathway_option = 'DLM', met_pathway_cutoff, null)) as met_dlm,
            max(
                if(pathway_option = 'Portfolio', met_pathway_cutoff, null)
            ) as met_portfolio,
            max(if(pathway_option = 'NJGPA', met_pathway_cutoff, null)) as met_njgpa,
            max(if(pathway_option = 'ACT', met_pathway_cutoff, null)) as met_act,
            max(if(pathway_option = 'SAT', met_pathway_cutoff, null)) as met_sat,
            max(if(pathway_option = 'PSAT10', met_pathway_cutoff, null)) as met_psat10,
            max(
                if(pathway_option = 'PSAT NMSQT', met_pathway_cutoff, null)
            ) as met_psat_nmsqt,

            /* sitting the njgpa at least once is a prerequisite for every other
               pathway to count */
            case
                when discipline = 'ELA' and attempted_njgpa_ela
                then true
                when discipline = 'Math' and attempted_njgpa_math
                then true
                else false
            end as njgpa_attempt,

        from {{ ref("int_students__graduation_pathway_scores") }}
        where scale_score is not null
        group by
            _dbt_source_project,
            student_number,
            discipline,
            ps_grad_path_code,
            attempted_njgpa_ela,
            attempted_njgpa_math
    ),

    discipline_met as (
        select
            student_number,
            discipline,

            case
                when ps_grad_path_code = 'M'
                then met_dlm
                else
                    met_dlm
                    or met_portfolio
                    or met_njgpa
                    or met_act
                    or met_sat
                    or met_psat10
                    or met_psat_nmsqt
            end as met_discipline,

            if(ps_grad_path_code = 'M', true, njgpa_attempt) as counts_toward_subject,

        from calcs
    ),

    met_subject as (
        /* a student's overall standing in each subject, however they got there */
        select
            student_number,

            max(if(discipline = 'ELA', met_discipline, null)) as met_ela,
            max(if(discipline = 'Math', met_discipline, null)) as met_math,
        from discipline_met
        where counts_toward_subject
        group by student_number
    ),

    roster as (
        select
            s.* except (attempted_njgpa_ela, attempted_njgpa_math),

            coalesce(s.attempted_njgpa_ela, false) as attempted_njgpa_ela,
            coalesce(s.attempted_njgpa_math, false) as attempted_njgpa_math,

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

        from {{ ref("int_students__graduation_pathway_scores") }} as s
        left join
            calcs as u
            on s.student_number = u.student_number
            and s.discipline = u.discipline
            and s._dbt_source_project = u._dbt_source_project
        left join met_subject as m on s.student_number = m.student_number
    ),

    eligibility as (
        select
            r.*,

            (r.met_ela and r.attempted_njgpa_ela) as counts_ela,
            (r.met_math and r.attempted_njgpa_math) as counts_math,

            (r.grade_level = 12 and r.fafsa_season_12th) as fafsa_required,

            (
                not r.attempted_njgpa_ela and not r.attempted_njgpa_math
            ) as attempted_nothing,

            /* the alternative pathways, in the order New Jersey prefers them.
               coalesce returns the first that was met. */
            coalesce(
                if(r.met_act, 'E', null),
                if(r.met_sat, 'D', null),
                if(r.met_psat10, 'J', null),
                if(r.met_psat_nmsqt, 'K', null)
            ) as best_alternative_code,
        from roster as r
    ),

    coded as (
        select
            r.*,

            case
                when r.grade_level <= 10
                then r.ps_grad_path_code
                when r.ps_grad_path_code in ('M', 'N', 'O', 'P')
                then r.ps_grad_path_code
                when r.met_njgpa
                then 'S'
                when r.njgpa_attempt
                then coalesce(r.best_alternative_code, 'R')
                else 'R'
            end as final_grad_path_code,
        from eligibility as r
    )

select
    r.* except (
        counts_ela,
        counts_math,
        fafsa_required,
        attempted_nothing,
        best_alternative_code
    ),

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
        r.final_grad_path_code
        when 'D'
        then 'SAT'
        when 'E'
        then 'ACT'
        when 'J'
        then 'PSAT10'
        when 'K'
        then 'PSAT NMSQT'
        when 'M'
        then 'DLM'
        when 'N'
        then 'Portfolio'
        when 'O'
        then 'Met No Requirements'
        when 'P'
        then 'Incomplete Credits'
        when 'R'
        then 'Default'
        when 'S'
        then 'NJGPA'
    end as final_grad_path_name,

    case
        when r.grade_level <= 10
        then 'Grad Eligible'
        when r.counts_ela and r.counts_math and r.fafsa_required and not r.has_fafsa
        then 'No FAFSA'
        when r.counts_ela and r.counts_math
        then 'Grad Eligible'
        when r.counts_ela and r.fafsa_required and not r.has_fafsa
        then 'ELA Only / No FAFSA'
        when r.counts_ela
        then 'ELA Only'
        when r.counts_math and r.fafsa_required and not r.has_fafsa
        then 'Math Only / No FAFSA'
        when r.counts_math
        then 'Math Only'
        when r.has_fafsa and r.fafsa_required
        then 'FAFSA Only'
        /* An 11th grader holding NJGPA records already is treated like a 12th
           grader, minus the FAFSA requirement -- testing ahead of their peers
           usually means they are behind on credits and belong in 12th grade.
           The grace below is only for those with no records yet. */
        when r.grade_level = 11 and r.attempted_nothing and not r.njgpa_season_11th
        then 'Grad Eligible'
        else 'Not Grad Eligible'
    end as grad_eligibility,

    row_number() over (
        partition by r.student_number, r.discipline order by r.pathway_option
    ) as rn_discipline_distinct,

from coded as r
where r.enroll_status = 0
