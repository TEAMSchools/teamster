with
    /* grain projection: determined by assessment_id + raw_score_low. Guards a
       future per-grade scaffold split; no-op today. */
    conversion as (
        select distinct
            c.assessment_id,
            c.academic_year,
            c.scope,
            c.scope_round,
            c.subject,
            c.grade_level,
            c.raw_score_low,
            c.raw_score_high,
            c.scale_score,
            c.aligned_scale_score,
            c.score_type,
            c.expected_total_subjects_tested,

            s.expected_test_type as test_type,
            s.expected_aligned_scope as aligned_scope,
            s.expected_subject_area as subject_area,
            s.expected_aligned_subject_area as aligned_subject_area,
            s.expected_grouping as `grouping`,
            s.expected_course_discipline as course_discipline,

        from
            {{ ref("stg_google_sheets__kippfwd__practice_scale_score_conversion") }}
            as c
        inner join
            {{ ref("stg_google_sheets__kippfwd__scaffold") }} as s
            on c.academic_year = s.academic_year
            and c.scope = s.expected_scope
            and c.score_type = s.expected_score_type
        where s.expected_test_type = 'Practice'
    ),

    responses as (
        select
            a.academic_year,
            a.illuminate_student_id,
            a.powerschool_student_number,
            a.assessment_id,
            a.title as assessment_title,
            a.date_taken as test_date,
            a.response_type_description,  -- Group name
            /* Points earned... looks to be # of questions correct on Illuminate */
            a.points,

            ssk.test_type,
            ssk.scope,
            ssk.aligned_scope,
            ssk.scope_round,
            ssk.grade_level,
            ssk.subject,
            ssk.subject_area,
            ssk.aligned_subject_area,
            ssk.`grouping`,
            ssk.score_type,
            ssk.expected_total_subjects_tested,
            ssk.course_discipline,

            initcap(a.response_type) as response_type,  -- Group or overall

            format_date('%B', a.date_taken) as test_month,

            round(a.percent_correct / 100, 2) as percent_correct,

            concat(
                format_date('%b', a.administered_at),
                ' ',
                format_date('%g', a.administered_at)
            ) as administration_round,

            max(if(a.response_type = 'overall', a.points, null)) over (
                partition by
                    a.academic_year, a.powerschool_student_number, a.assessment_id
            ) as raw_score,

            max(if(a.response_type = 'overall', ssk.aligned_scale_score, null)) over (
                partition by
                    a.academic_year, a.powerschool_student_number, a.assessment_id
            ) as scale_score,

            count(distinct ssk.subject_area) over (
                partition by
                    a.academic_year,
                    a.powerschool_student_number,
                    ssk.scope_round,
                    ssk.grade_level
            ) as actual_total_subjects_tested,

        from {{ ref("int_assessments__response_rollup") }} as a
        inner join
            -- `a.assessment_id` is canonical_assessment_id (response_rollup
            -- output is canonical-grain). Sheet's assessment_id values
            -- currently align to canonical (12/12 sheet ids = canonical) since
            -- Practice SAT/ACT haven't been canonicalized into multi-member
            -- groups. If multipart Practice administrations are added later,
            -- the sheet must reference the canonical (lowest) assessment_id.
            conversion as ssk
            on a.assessment_id = ssk.assessment_id
            and a.points between ssk.raw_score_low and ssk.raw_score_high
        where a.response_type in ('group', 'overall')
    ),

    scores as (
        -- group scores
        select
            academic_year,
            powerschool_student_number,
            scope,
            aligned_scope,
            scope_round,
            test_type,
            grade_level,
            assessment_id,
            assessment_title,
            administration_round,
            course_discipline,
            test_date,
            test_month,
            response_type,
            response_type_description,
            `subject`,
            subject_area,
            aligned_subject_area,
            `grouping`,
            score_type,
            points,
            percent_correct,
            actual_total_subjects_tested,
            expected_total_subjects_tested,
            raw_score,
            scale_score,

        from responses
        where response_type = 'Group'

        union all

        -- subject scores
        select
            academic_year,
            powerschool_student_number,
            scope,
            aligned_scope,
            scope_round,
            test_type,
            grade_level,
            assessment_id,
            assessment_title,
            administration_round,
            course_discipline,
            test_date,
            test_month,

            'Subject' as response_type,
            'Subject Score' as response_type_description,

            `subject`,
            subject_area,
            aligned_subject_area,
            `grouping`,
            score_type,

            null as points,
            null as percent_correct,

            actual_total_subjects_tested,
            expected_total_subjects_tested,
            raw_score,
            scale_score,

        from responses
        where response_type = 'Overall'

        union all

        -- total scores
        select
            academic_year,
            powerschool_student_number,
            scope,
            aligned_scope,
            scope_round,
            test_type,
            grade_level,

            null as assessment_id,
            'NA' as assessment_title,

            administration_round,

            'NA' as course_discipline,

            max(test_date) as test_date,

            format_date('%B', max(test_date)) as test_month,

            'Total' as response_type,
            'Total Score' as response_type_description,
            null as subject,

            if(scope = 'ACT', 'Composite', 'Combined') as subject_area,

            'Total' as aligned_subject_area,
            'Total' as `grouping`,

            case
                scope
                when 'ACT'
                then 'act_composite'
                when 'SAT'
                then 'sat_total_score'
                when 'PSAT 8/9'
                then 'psat89_total'
                when 'PSAT10'
                then 'psat10_total'
                when 'PSAT NMSQT'
                then 'psatnmsqt_total'
            end as score_type,

            sum(points) as points,

            null as percent_correct,

            actual_total_subjects_tested,
            expected_total_subjects_tested,

            sum(points) as raw_score,

            round(
                case
                    when actual_total_subjects_tested != expected_total_subjects_tested
                    then null
                    when scope = 'ACT'
                    then avg(scale_score)
                    else sum(scale_score)
                end,
                0
            ) as scale_score,

        from responses
        where response_type = 'Overall'
        group by
            academic_year,
            powerschool_student_number,
            scope,
            aligned_scope,
            scope_round,
            test_type,
            grade_level,
            administration_round,
            actual_total_subjects_tested,
            expected_total_subjects_tested
    )

select
    *,

    /* response_type stays in the partition so group rows rank among themselves
       and never displace the subject row before being nulled. */
    if(
        response_type = 'Group',
        null,
        row_number() over (
            partition by powerschool_student_number, scope, score_type, response_type
            order by scale_score desc
        )
    ) as rn_highest,

from scores
