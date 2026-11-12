-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause N1 = cube: Cube keeps internal assessments only (is_internal_assessment), and this assessment is not one
-- cause D1 = cube: replacement scores (is_replacement) are left out of Cube's score anchors
-- cause D2 = cube: the student has a section in the subject, but none spans the assessment's anchor date, and no homeroom does
-- cause D3 = cube: the student has no section in the subject and no homeroom on the anchor date
-- cause D4 = cube: the resolved section's student enrollment key has no row in dim_student_enrollments, so Cube cannot reach the student's school
-- cause D5 = cube: the score's enrollment stint has no bucket span for the subject, so Cube reads Bucket 4, while the dashboard takes the student's latest bucket assignment of the year
-- reproduce N1:
--  SELECT d.grade_level, d.nj_student_tier, COUNT(*) AS n_rows
--  FROM `teamster-332318`.`kipptaf_tableau`.`rpt_tableau__assessment_dashboard` AS d
--  WHERE d.academic_year = 2026 AND d.response_type = 'overall' AND NOT d.is_normed_scope
--    AND d.nj_student_tier IN ('Bucket 1', 'Bucket 2', 'Bucket 3')
--  GROUP BY d.grade_level, d.nj_student_tier
-- reproduce D1:
--  SELECT d.region, COUNT(*) AS n_rows
--  FROM `teamster-332318`.`kipptaf_tableau`.`rpt_tableau__assessment_dashboard` AS d
--  WHERE d.academic_year = 2026 AND d.response_type = 'overall' AND d.is_normed_scope AND d.is_replacement
--  GROUP BY d.region
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
-- reproduce D5:
--  SELECT a.bucket_subject, se.grade_level, COUNT(*) AS n_rows
--  FROM `teamster-332318`.`kipptaf_marts`.`fct_assessment_scores_enrollment_scoped` AS f
--  INNER JOIN `teamster-332318`.`kipptaf_marts`.`dim_dates` AS dd ON f.assessment_date_key = dd.date_key
--  INNER JOIN `teamster-332318`.`kipptaf_marts`.`dim_assessment_administrations` AS aa
--    ON f.assessment_administration_key = aa.assessment_administration_key
--  INNER JOIN `teamster-332318`.`kipptaf_marts`.`dim_assessments` AS a ON aa.assessment_key = a.assessment_key
--  INNER JOIN `teamster-332318`.`kipptaf_marts`.`dim_student_section_enrollments` AS sse
--    ON f.student_section_enrollment_key = sse.student_section_enrollment_key
--  INNER JOIN `teamster-332318`.`kipptaf_marts`.`dim_student_enrollments` AS se
--    ON sse.student_enrollment_key = se.student_enrollment_key
--  LEFT JOIN `teamster-332318`.`kipptaf_marts`.`dim_student_bucket_status` AS bs
--    ON se.student_enrollment_key = bs.student_enrollment_key AND bs.subject = a.bucket_subject AND bs.is_latest_in_enrollment
--  WHERE dd.academic_year = 2026 AND a.is_internal_assessment AND f.response_type = 'overall'
--    AND a.bucket_subject IN ('Reading', 'Math') AND bs.subject IS NULL
--  GROUP BY a.bucket_subject, se.grade_level

-- One proof for the dashboard_only bucket of all 8 bucket comparisons
-- (students-bucket-1/2/3-module, students-buckets-1-2-module and the 4
-- mastery-* twins). No predicate names a bucket, so the same SQL serves each;
-- confirm stores it once per comparison.
with
    -- the dashboard's rows for the comparison's year, by the row key
    dashboard as (
        select
            cast(student_number as string) as sn,
            cast(assessment_id as string) as aid,
            response_type,
            standard_code,
            count(*) as n_rows,
            -- is_normed_scope is asr.is_internal_assessment
            countif(is_normed_scope) as n_internal,
            countif(is_replacement) as n_replacement,
        from `teamster-332318`.`kipptaf_tableau`.`rpt_tableau__assessment_dashboard`
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

    -- the bucket subject each assessment reads (int_assessments__assessments_members)
    bucket_subjects as (
        -- grain projection, not dup-masking: one subject per source and assessment
        select distinct source, canonical_assessment_id, bucket_subject,
        from `teamster-332318`.`kipptaf_assessments`.`int_assessments__assessments_members`
    ),

    -- Cube's 2026 rows per student and assessment, rebuilt from the resolver
    -- and the enrollment chain the scores fact reads, with the bucket the
    -- scores cube's `bucket` reads (CASE bucket_subject WHEN 'Reading' THEN
    -- ela_bucket WHEN 'Math' THEN math_bucket) and whether
    -- dim_student_enrollment_status found a span (coalesce(mb.bucket,
    -- 'Bucket 4') on mb.is_latest_in_enrollment)
    cube_buckets as (
        select
            cast(r.student_number as string) as sn,
            cast(r.canonical_assessment_id as string) as aid,
            count(*) as n_rows,
            countif(
                bs.subject is null
                and case
                    m.bucket_subject
                    when 'Reading'
                    then es.ela_bucket
                    when 'Math'
                    then es.math_bucket
                end
                = 'Bucket 4'
            ) as n_default_bucket,
        from `teamster-332318`.`kipptaf_assessments`.`int_assessments__resolved_section_enrollments` as r
        inner join
            `teamster-332318`.`kipptaf_marts`.`dim_student_section_enrollments` as sse
            on r.student_section_enrollment_key = sse.student_section_enrollment_key
        inner join
            `teamster-332318`.`kipptaf_marts`.`dim_student_enrollments` as se
            on sse.student_enrollment_key = se.student_enrollment_key
        inner join
            bucket_subjects as m
            on r.source = m.source
            and r.canonical_assessment_id = m.canonical_assessment_id
        left join
            `teamster-332318`.`kipptaf_marts`.`dim_student_enrollment_status` as es
            on se.student_enrollment_key = es.student_enrollment_key
        left join
            `teamster-332318`.`kipptaf_marts`.`dim_student_bucket_status` as bs
            on se.student_enrollment_key = bs.student_enrollment_key
            and m.bucket_subject = bs.subject
            and bs.is_latest_in_enrollment
        where r.source_type = 'internal' and se.academic_year = 2026
        group by 1, 2
    )

select
    u.__row,
    case
        -- fct_assessment_scores_enrollment_scoped: where rr.is_internal_assessment
        when d.n_rows > 0 and d.n_internal = 0
        then 'N1'
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
        -- Cube holds the row in 2026, but every copy reads the default
        -- Bucket 4: dim_student_enrollment_status found no
        -- is_latest_in_enrollment span for the stint and subject
        when b.n_rows > 0 and b.n_default_bucket = b.n_rows
        then 'D5'
        else 'UNEXPLAINED'
    end as cause,
from {unmatched} as u
left join
    dashboard as d
    on cast(u.lea_student_identifier as string) = d.sn
    and cast(u.source_assessment_id as string) = d.aid
    and u.response_type is not distinct from d.response_type
    and u.response_type_code is not distinct from d.standard_code
left join
    scope as c
    on cast(u.lea_student_identifier as string) = c.sn
    and cast(u.source_assessment_id as string) = c.aid
left join
    cube_buckets as b
    on cast(u.lea_student_identifier as string) = b.sn
    and cast(u.source_assessment_id as string) = b.aid
