-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause M1 = dashboard: the student's enrollment changed (grade or school): Cube files the score by the enrollment its resolved section belongs to, the dashboard by the enrollment week it was given in, and the two disagree
-- reproduce M1:
--  WITH cube_enrollment AS (
--    SELECT r.student_number, r.canonical_assessment_id, se.grade_level, l.abbreviation AS school
--    FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__resolved_section_enrollments` AS r
--    INNER JOIN `teamster-332318`.`kipptaf_marts`.`dim_student_section_enrollments` AS sse
--      ON r.student_section_enrollment_key = sse.student_section_enrollment_key
--    INNER JOIN `teamster-332318`.`kipptaf_marts`.`dim_student_enrollments` AS se
--      ON sse.student_enrollment_key = se.student_enrollment_key
--    INNER JOIN `teamster-332318`.`kipptaf_marts`.`dim_locations` AS l
--      ON se.location_key = l.location_key
--    WHERE r.source_type = 'internal'),
--  scores AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup`
--    WHERE academic_year = 2026 AND is_internal_assessment),
--  eligible_weeks AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks`
--    WHERE is_enrolled_week_end AND enroll_status IN (0, 2, 3) AND NOT is_out_of_district)
--  SELECT w.school, COUNT(*) AS n_rows
--  FROM scores AS s
--  INNER JOIN cube_enrollment AS c
--    ON c.student_number = s.student_number AND c.canonical_assessment_id = s.assessment_id
--  INNER JOIN eligible_weeks AS w
--    ON w.student_number = s.student_number AND w.academic_year = s.academic_year
--    AND w.region = s.region AND s.administered_at BETWEEN w.week_start_monday AND w.week_end_sunday
--  WHERE c.grade_level != w.grade_level OR c.school != w.school
--  GROUP BY w.school

with
    -- Cube's cell: the student enrollment the resolved section points to
    cube_enrollment as (
        select
            cast(r.student_number as string) as sn,
            cast(r.canonical_assessment_id as string) as aid,
            count(distinct format('%T|%T', se.grade_level, l.abbreviation)) as n_cells,
            min(se.grade_level) as grade_level,
            min(l.abbreviation) as school,
        from `teamster-332318`.`kipptaf_assessments`.`int_assessments__resolved_section_enrollments` as r
        inner join
            `teamster-332318`.`kipptaf_marts`.`dim_student_section_enrollments` as sse
            on r.student_section_enrollment_key = sse.student_section_enrollment_key
        inner join
            `teamster-332318`.`kipptaf_marts`.`dim_student_enrollments` as se
            on sse.student_enrollment_key = se.student_enrollment_key
        inner join
            `teamster-332318`.`kipptaf_marts`.`dim_locations` as l
            on se.location_key = l.location_key
        where r.source_type = 'internal'
        group by 1, 2
    ),

    -- one administration per student and assessment, as the dashboard joins it
    administrations as (
        select
            cast(student_number as string) as sn,
            cast(assessment_id as string) as aid,
            count(
                distinct format('%T|%T|%T', academic_year, region, administered_at)
            ) as n_administrations,
            min(academic_year) as academic_year,
            min(region) as region,
            min(administered_at) as administered_at,
        from `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup`
        group by 1, 2
    ),

    -- the dashboard's cell: the enrollment week rows covering the
    -- administration that pass rpt_tableau__ddi_dashboard's filters
    dashboard_week as (
        select
            a.sn,
            a.aid,
            count(distinct format('%T|%T', w.grade_level, w.school)) as n_cells,
            min(w.grade_level) as grade_level,
            min(w.school) as school,
        from administrations as a
        inner join
            `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks` as w
            on cast(w.student_number as string) = a.sn
            and w.academic_year = a.academic_year
            and w.region = a.region
            and a.administered_at between w.week_start_monday and w.week_end_sunday
        where
            a.n_administrations = 1
            and w.is_enrolled_week_end
            and w.enroll_status in (0, 2, 3)
            and not w.is_out_of_district
        group by 1, 2
    )

select
    u.__row,
    case
        when
            c.n_cells = 1
            and d.n_cells = 1
            and (c.grade_level != d.grade_level or c.school != d.school)
        then 'M1'
        else 'UNEXPLAINED'
    end as cause,
from {unmatched} as u
left join
    cube_enrollment as c
    on cast(u.lea_student_identifier as string) = c.sn
    and cast(u.source_assessment_id as string) = c.aid
left join
    dashboard_week as d
    on cast(u.lea_student_identifier as string) = d.sn
    and cast(u.source_assessment_id as string) = d.aid
