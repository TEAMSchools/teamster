-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause D1 = cube: replacement scores (is_replacement) are left out of Cube's score anchors
-- cause D2 = cube: the student has a section in the subject, but none spans the assessment's anchor date, and no homeroom does
-- cause D3 = cube: the student has no section in the subject and no homeroom on the anchor date
-- cause D4 = cube: the resolved section's student enrollment key has no row in dim_student_enrollments, so Cube cannot reach the student's school
-- cause I1 = cube: the student's IEP status differs: Cube reads no IEP from the enrollment its resolved section belongs to, the dashboard reads Has IEP from the enrollment week, so the score falls in a different IEP scope on each side
-- reproduce D1:
--  SELECT d.school, COUNT(*) AS n_rows
--  FROM `teamster-332318`.`kipptaf_tableau`.`rpt_tableau__ddi_dashboard` AS d
--  WHERE d.academic_year = 2026 AND d.is_replacement
--  GROUP BY d.school
-- reproduce D2:
--  WITH anchors AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__score_anchors`
--    WHERE source_type = 'internal' AND anchor_date >= DATE '2026-07-01'),
--  sections AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__course_enrollments` WHERE cc_dcid IS NOT NULL),
--  homerooms AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__course_enrollments` WHERE cc_dcid IS NOT NULL AND courses_credittype = 'HR')
--  SELECT s._dbt_source_project, COUNT(*) AS n_scores
--  FROM anchors AS s
--  WHERE EXISTS (
--      SELECT ce.subject_area FROM sections AS ce
--      WHERE ce.student_number = s.student_number AND ce._dbt_source_project = s._dbt_source_project
--        AND ce.subject_area = s.subject_area)
--    AND NOT EXISTS (
--      SELECT ce.subject_area FROM sections AS ce
--      WHERE ce.student_number = s.student_number AND ce._dbt_source_project = s._dbt_source_project
--        AND ce.subject_area = s.subject_area
--        AND s.anchor_date >= ce.cc_dateenrolled AND s.anchor_date < ce.cc_dateleft)
--    AND NOT EXISTS (
--      SELECT h.subject_area FROM homerooms AS h
--      WHERE h.student_number = s.student_number AND h._dbt_source_project = s._dbt_source_project
--        AND s.anchor_date >= h.cc_dateenrolled AND s.anchor_date < h.cc_dateleft)
--  GROUP BY s._dbt_source_project
-- reproduce D3:
--  WITH anchors AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__score_anchors`
--    WHERE source_type = 'internal' AND anchor_date >= DATE '2026-07-01'),
--  sections AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__course_enrollments` WHERE cc_dcid IS NOT NULL),
--  homerooms AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__course_enrollments` WHERE cc_dcid IS NOT NULL AND courses_credittype = 'HR')
--  SELECT s._dbt_source_project, COUNT(*) AS n_scores
--  FROM anchors AS s
--  WHERE NOT EXISTS (
--      SELECT ce.subject_area FROM sections AS ce
--      WHERE ce.student_number = s.student_number AND ce._dbt_source_project = s._dbt_source_project
--        AND ce.subject_area = s.subject_area)
--    AND NOT EXISTS (
--      SELECT h.subject_area FROM homerooms AS h
--      WHERE h.student_number = s.student_number AND h._dbt_source_project = s._dbt_source_project
--        AND s.anchor_date >= h.cc_dateenrolled AND s.anchor_date < h.cc_dateleft)
--  GROUP BY s._dbt_source_project
-- reproduce D4:
--  WITH anchors AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__score_anchors`
--    WHERE source_type = 'internal' AND anchor_date >= DATE '2026-07-01'),
--  resolved AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__resolved_section_enrollments`
--    WHERE source_type = 'internal')
--  SELECT r.region, COUNT(*) AS n_scores
--  FROM resolved AS r
--  INNER JOIN `teamster-332318`.`kipptaf_marts`.`dim_student_section_enrollments` AS sse
--    ON r.student_section_enrollment_key = sse.student_section_enrollment_key
--  WHERE NOT EXISTS (
--      SELECT se.location_key FROM `teamster-332318`.`kipptaf_marts`.`dim_student_enrollments` AS se
--      WHERE se.student_enrollment_key = sse.student_enrollment_key)
--    AND EXISTS (
--      SELECT s.subject_area FROM anchors AS s
--      WHERE s.student_number = r.student_number AND s.source = r.source
--        AND s.canonical_assessment_id = r.canonical_assessment_id
--        AND s._dbt_source_project = r._dbt_source_project)
--  GROUP BY r.region
-- reproduce I1:
--  WITH cube_iep AS (
--    SELECT r.student_number, r.canonical_assessment_id, es.is_iep
--    FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__resolved_section_enrollments` AS r
--    INNER JOIN `teamster-332318`.`kipptaf_marts`.`dim_student_section_enrollments` AS sse
--      ON r.student_section_enrollment_key = sse.student_section_enrollment_key
--    LEFT JOIN `teamster-332318`.`kipptaf_marts`.`dim_student_enrollment_status` AS es
--      ON sse.student_enrollment_key = es.student_enrollment_key
--    WHERE r.source_type = 'internal'),
--  scores AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup`
--    WHERE academic_year = 2026 AND is_internal_assessment),
--  iep_weeks AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks`
--    WHERE is_enrolled_week_end AND enroll_status IN (0, 2, 3) AND NOT is_out_of_district
--      AND iep_status = 'Has IEP')
--  SELECT w.school, COUNT(*) AS n_rows
--  FROM scores AS s
--  INNER JOIN cube_iep AS c
--    ON c.student_number = s.student_number AND c.canonical_assessment_id = s.assessment_id
--  INNER JOIN iep_weeks AS w
--    ON w.student_number = s.student_number AND w.academic_year = s.academic_year
--    AND w.region = s.region AND s.administered_at BETWEEN w.week_start_monday AND w.week_end_sunday
--  WHERE NOT COALESCE(c.is_iep, FALSE)
--  GROUP BY w.school

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
            countif(iep_status = 'Has IEP') as n_has_iep,
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
    ),

    -- IEP status on each side: Cube's from the enrollment the resolved
    -- section belongs to (dim_student_enrollment_status), the dashboard's from
    -- the enrollment week row covering the administration
    iep_sides as (
        select
            cast(r.student_number as string) as sn,
            cast(r.canonical_assessment_id as string) as aid,
            logical_or(es.is_iep) as cube_any_iep,
            logical_and(not coalesce(es.is_iep, false)) as cube_no_iep,
        from `teamster-332318`.`kipptaf_assessments`.`int_assessments__resolved_section_enrollments` as r
        inner join
            `teamster-332318`.`kipptaf_marts`.`dim_student_section_enrollments` as sse
            on r.student_section_enrollment_key = sse.student_section_enrollment_key
        left join
            `teamster-332318`.`kipptaf_marts`.`dim_student_enrollment_status` as es
            on sse.student_enrollment_key = es.student_enrollment_key
        where r.source_type = 'internal'
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
        -- Cube's enrollment status says no IEP; the dashboard's week row says
        -- Has IEP, so the row falls in a different IEP scope on each side
        when i.cube_no_iep and d.n_rows > 0 and d.n_has_iep = d.n_rows
        then 'I1'
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

left join
    iep_sides as i
    on cast(u.lea_student_identifier as string) = i.sn
    and cast(u.source_assessment_id as string) = i.aid
