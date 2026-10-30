-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause D1 = cube: replacement scores (is_replacement) are left out of Cube's score anchors
-- cause D2 = cube: the student has a section in the subject, but none spans the assessment's anchor date, and no homeroom does
-- cause D3 = cube: the student has no section in the subject and no homeroom on the anchor date
-- cause D4 = cube: the resolved section's student enrollment key has no row in dim_student_enrollments, so Cube cannot reach the student's school

with
    -- the dashboard's rows for the comparison's year, by the row key
    dashboard as (
        select
            cast(student_number as string) as sn,
            cast(assessment_id as string) as aid,
            response_type,
            response_type_code,
            count(*) as n_rows,
            countif(is_replacement) as n_replacement,
        from `teamster-332318`.`kipptaf_tableau`.`rpt_tableau__ddi_dashboard`
        where academic_year = 2026
        group by 1, 2, 3, 4
    ),

    -- Cube's internal score anchors (int_assessments__score_anchors), each with
    -- what the resolver (int_assessments__resolved_section_enrollments) finds
    anchors as (
        select
            cast(s.student_number as string) as sn,
            cast(s.canonical_assessment_id as string) as aid,
            s.source,
            s._dbt_source_project,
            logical_or(
                ce.subject_area = s.subject_area and ce.cc_dcid is not null
            ) as has_subject_section,
            logical_or(
                ce.subject_area = s.subject_area
                and ce.cc_dcid is not null
                and s.anchor_date >= ce.cc_dateenrolled
                and s.anchor_date < ce.cc_dateleft
            ) as has_subject_section_on_date,
            logical_or(
                ce.courses_credittype = 'HR'
                and ce.cc_dcid is not null
                and s.anchor_date >= ce.cc_dateenrolled
                and s.anchor_date < ce.cc_dateleft
            ) as has_homeroom_on_date,
        from `teamster-332318`.`kipptaf_assessments`.`int_assessments__score_anchors` as s
        left join
            `teamster-332318`.`kipptaf_assessments`.`int_assessments__course_enrollments` as ce
            on s.student_number = ce.student_number
            and s._dbt_source_project = ce._dbt_source_project
        where s.source_type = 'internal'
        group by 1, 2, 3, 4
    ),

    -- the resolved section, and whether the dimension chain Cube reads it
    -- through (section enrollment -> student enrollment) holds a row
    resolved as (
        select
            cast(r.student_number as string) as sn,
            cast(r.canonical_assessment_id as string) as aid,
            r.source,
            r._dbt_source_project,
            logical_or(sse.student_section_enrollment_key is not null) as has_section_row,
            logical_or(se.student_enrollment_key is not null) as has_enrollment_row,
        from `teamster-332318`.`kipptaf_assessments`.`int_assessments__resolved_section_enrollments` as r
        left join
            `teamster-332318`.`kipptaf_marts`.`dim_student_section_enrollments` as sse
            on r.student_section_enrollment_key = sse.student_section_enrollment_key
        left join
            `teamster-332318`.`kipptaf_marts`.`dim_student_enrollments` as se
            on sse.student_enrollment_key = se.student_enrollment_key
        where r.source_type = 'internal'
        group by 1, 2, 3, 4
    ),

    -- per student and assessment, across sources and projects
    scope as (
        select
            a.sn,
            a.aid,
            count(*) as n_anchors,
            countif(r.sn is not null) as n_resolved,
            logical_or(r.has_section_row) as any_section_row,
            logical_or(r.has_enrollment_row) as any_enrollment_row,
            logical_and(a.has_subject_section) as all_have_subject_section,
            logical_or(a.has_subject_section) as any_has_subject_section,
            logical_or(a.has_subject_section_on_date) as any_subject_on_date,
            logical_or(a.has_homeroom_on_date) as any_homeroom_on_date,
        from anchors as a
        left join
            resolved as r
            on a.sn = r.sn
            and a.aid = r.aid
            and a.source = r.source
            and a._dbt_source_project = r._dbt_source_project
        group by 1, 2
    )

select
    u.__row,
    case
        -- score_anchors: where sc.is_internal_assessment and not sc.is_replacement
        when d.n_rows > 0 and d.n_replacement = d.n_rows
        then 'D1'
        -- resolver: no subject section spans the anchor date, and no homeroom does
        when
            c.n_anchors > 0
            and c.n_resolved = 0
            and c.all_have_subject_section
            and not c.any_subject_on_date
            and not c.any_homeroom_on_date
        then 'D2'
        when
            c.n_anchors > 0
            and c.n_resolved = 0
            and not c.any_has_subject_section
            and not c.any_homeroom_on_date
        then 'D3'
        -- resolved, but the section's student enrollment key has no row in
        -- dim_student_enrollments, so Cube cannot reach the student's school
        when
            c.n_resolved > 0
            and c.any_section_row
            and not coalesce(c.any_enrollment_row, false)
        then 'D4'
        else 'UNEXPLAINED'
    end as cause,
from {unmatched} as u
left join
    dashboard as d
    on cast(u.lea_student_identifier as string) = d.sn
    and cast(u.source_assessment_id as string) = d.aid
    and u.response_type is not distinct from d.response_type
    and u.response_type_code is not distinct from d.response_type_code
left join
    scope as c
    on cast(u.lea_student_identifier as string) = c.sn
    and cast(u.source_assessment_id as string) = c.aid
