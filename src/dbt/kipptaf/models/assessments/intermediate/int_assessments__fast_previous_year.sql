with
    prev_year as (
        select
            co.academic_year,
            co.student_number,
            co.grade_level,

            pp.student_id,
            pp.assessment_subject,
            pp.scale_score as prev_pm3_scale,
            pp.achievement_level as prev_pm3_achievement_level,
            pp.achievement_level_int as prev_pm3_level_int,

            cw.sublevel_name as prev_pm3_sublevel_name,
            cw.sublevel_number as prev_pm3_sublevel_number,

            round(
                rank() over (
                    partition by
                        pp.academic_year, pp.assessment_grade, pp.assessment_subject
                    order by pp.scale_score asc
                ) / count(*) over (
                    partition by
                        pp.academic_year, pp.assessment_grade, pp.assessment_subject
                ),
                4
            ) as fldoe_percentile_rank,
        from {{ ref("int_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("stg_fldoe__fast") }} as pp
            on co.fleid = pp.student_id
            and (co.academic_year - 1) = pp.academic_year
            and pp.administration_window = 'PM3'
        left join
            {{ ref("stg_assessments__iready_crosswalk") }} as cw
            on pp.assessment_subject = cw.test_name
            and pp.assessment_grade = cw.grade_level
            and pp.scale_score between cw.scale_low and cw.scale_high
            and cw.source_system = 'FAST_NEW'
            and cw.destination_system = 'FL'
        where co.rn_year = 1 and co.region = 'Miami' and co.grade_level != 99
    )

select
    py.student_number,
    py.academic_year,
    py.grade_level,
    py.student_id,
    py.assessment_subject,
    py.prev_pm3_scale,
    py.prev_pm3_achievement_level,
    py.prev_pm3_level_int,
    py.prev_pm3_sublevel_name,
    py.prev_pm3_sublevel_number,
    py.fldoe_percentile_rank,

    cw1.scale_low as scale_for_growth,
    cw1.sublevel_name as sublevel_for_growth,
    cw1.sublevel_number as sublevel_number_for_growth,

    cw2.scale_low as scale_for_proficiency,

    case
        when py.prev_pm3_level_int = 5 and cw4.sublevel_number = 8
        then null
        when
            py.prev_pm3_level_int between 3 and 4
            and py.prev_pm3_sublevel_number = cw4.sublevel_number
        then 1
        else cw1.scale_low - py.prev_pm3_scale
    end as scale_points_to_growth_pm3,

    if(
        cw2.scale_low - py.prev_pm3_scale <= 0, null, cw2.scale_low - py.prev_pm3_scale
    ) as scale_points_to_proficiency_pm3,
from prev_year as py
/* gets FL sublevels & scale for growth */
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cw1
    on py.assessment_subject = cw1.test_name
    and py.grade_level = cw1.grade_level
    and (py.prev_pm3_sublevel_number + 1) = cw1.sublevel_number
    and cw1.source_system = 'FAST_NEW'
    and cw1.destination_system = 'FL'
/* gets proficient scale score */
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cw2
    on py.assessment_subject = cw2.test_name
    and py.grade_level = cw2.grade_level
    and cw2.source_system = 'FAST_NEW'
    and cw2.destination_system = 'FL'
    and cw2.sublevel_number = 6
/* gets growth scale for students scoring 3 or 4 */
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cw3
    on py.assessment_subject = cw3.test_name
    and py.grade_level = cw3.grade_level
    and py.prev_pm3_sublevel_number = cw3.sublevel_number
    and cw3.source_system = 'FAST_NEW'
    and cw3.destination_system = 'FL'
/* gets current year level for past year test */
left join
    {{ ref("stg_assessments__iready_crosswalk") }} as cw4
    on py.assessment_subject = cw4.test_name
    and py.grade_level = cw4.grade_level
    and py.prev_pm3_scale between cw4.scale_low and cw4.scale_high
    and cw4.source_system = 'FAST_NEW'
    and cw4.destination_system = 'FL'
