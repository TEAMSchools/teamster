with
    course_flag_options as (
        select column_name, option_id, code, label,
        from {{ ref("int_focus__custom_field_options") }}
        where source_class = 'StudentReportCardGrade'
    )

select
    g.id as student_report_card_grade_id,
    g.syear as academic_year,
    g.school_id as schoolid,
    g.student_id,
    g.marking_period_id,
    g.grad_subject_id,
    g.course_num,
    g.course_title,
    g.grade_title,
    g.gpa_points,
    g.weighted_gpa_points,
    g.credits,
    g.credits_earned,
    g.affects_gpa,
    g.carries_credits,
    g.course_history,
    g.grade_level,
    g.district_number,
    g.school_number,
    g.course_flag_1,
    g.course_flag_2,

    mkp.syear as marking_period_academic_year,
    mkp.title as marking_period_title,
    mkp.short_name as marking_period_short_name,
    mkp.type as marking_period_type,
    mkp.start_date as marking_period_start_date,
    mkp.end_date as marking_period_end_date,

    f1.label as course_flag_1_label,

    f2.label as course_flag_2_label,

from {{ ref("stg_focus__student_report_card_grades") }} as g
-- aliased mkp to match int_focus__schedule, where mp is already schedule's own
-- term-code column
left join
    {{ ref("stg_focus__marking_periods") }} as mkp
    on g.marking_period_id = mkp.marking_period_id
-- Course Flag 1 and 2 are the only decodable custom fields on this table, and
-- both read the same option list, so they are resolved with two joins here
-- rather than in a dedicated __pivot model. District and School have no option
-- rows and Gradelevel decodes to its own code, so none of the three is decoded.
left join
    course_flag_options as f1
    on g.course_flag_1 in (f1.option_id, f1.code)
    and f1.column_name = 'custom_1'
left join
    course_flag_options as f2
    on g.course_flag_2 in (f2.option_id, f2.code)
    and f2.column_name = 'custom_2'
