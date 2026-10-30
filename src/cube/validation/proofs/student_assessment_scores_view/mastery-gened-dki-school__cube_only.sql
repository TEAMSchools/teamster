-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause C1 = dashboard: WPP assessments are left off the dashboard (module_type = WPP)
-- cause C2 = dashboard: assessments with a blank module_type are left off the dashboard
-- cause C3 = dashboard: the response rollup dates the administration in a prior academic year, so the dashboard cannot place it in 2026
-- cause C4 = dashboard: the assessment was given before the student's first enrollment week, so no week row covers it
-- cause C5 = dashboard: the student was not enrolled at the end of the week the assessment was given
-- cause C5O = dashboard: the student was out of district that week
-- cause I1 = cube: the student's IEP status differs: Cube reads no IEP from the enrollment its resolved section belongs to, the dashboard reads Has IEP from the enrollment week, so the score falls in a different IEP scope on each side
-- reproduce C1:
--  SELECT r.region, COUNT(*) AS n_rows
--  FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup` AS r
--  WHERE r.academic_year = 2026 AND r.is_internal_assessment AND r.module_type = 'WPP'
--  GROUP BY r.region
-- reproduce C2:
--  SELECT r.region, COUNT(*) AS n_rows
--  FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup` AS r
--  WHERE r.academic_year = 2026 AND r.is_internal_assessment AND r.module_type IS NULL
--  GROUP BY r.region
-- reproduce C3:
--  SELECT r.region, COUNT(*) AS n_rows
--  FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup` AS r
--  INNER JOIN `teamster-332318`.`kipptaf_assessments`.`int_assessments__assessments_members` AS m
--    ON r.source = m.source AND r.assessment_id = m.assessment_id
--  INNER JOIN `teamster-332318`.`kipptaf_assessments`.`int_assessments__assessments_canonical` AS c
--    ON m.source = c.source AND m.canonical_assessment_id = c.canonical_assessment_id
--  WHERE r.is_internal_assessment AND r.module_type != 'WPP' AND r.academic_year < 2026
--    AND COALESCE(c.administered_date, r.date_taken) >= DATE '2026-07-01'
--  GROUP BY r.region
-- reproduce C4:
--  WITH scores AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup`
--    WHERE academic_year = 2026 AND is_internal_assessment AND module_type != 'WPP')
--  SELECT r.region, COUNT(*) AS n_rows
--  FROM scores AS r
--  WHERE NOT EXISTS (
--    SELECT w.region FROM `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks` AS w
--    WHERE w.student_number = r.student_number AND w.academic_year = r.academic_year
--      AND w.region = r.region AND w.week_start_monday <= r.administered_at)
--  GROUP BY r.region
-- reproduce C5:
--  WITH scores AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup`
--    WHERE academic_year = 2026 AND is_internal_assessment AND module_type != 'WPP')
--  SELECT r.region, COUNT(*) AS n_rows
--  FROM scores AS r
--  WHERE EXISTS (
--      SELECT w.region FROM `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks` AS w
--      WHERE w.student_number = r.student_number AND w.academic_year = r.academic_year
--        AND w.region = r.region AND r.administered_at BETWEEN w.week_start_monday AND w.week_end_sunday)
--    AND NOT EXISTS (
--      SELECT w.region FROM `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks` AS w
--      WHERE w.student_number = r.student_number AND w.academic_year = r.academic_year
--        AND w.region = r.region AND r.administered_at BETWEEN w.week_start_monday AND w.week_end_sunday
--        AND w.is_enrolled_week_end)
--  GROUP BY r.region
-- reproduce C5O:
--  WITH scores AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup`
--    WHERE academic_year = 2026 AND is_internal_assessment AND module_type != 'WPP'),
--  eligible AS (
--    SELECT * FROM `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks`
--    WHERE is_enrolled_week_end AND enroll_status IN (0, 2, 3))
--  SELECT r.region, COUNT(*) AS n_rows
--  FROM scores AS r
--  WHERE EXISTS (
--      SELECT w.region FROM eligible AS w
--      WHERE w.student_number = r.student_number AND w.academic_year = r.academic_year
--        AND w.region = r.region AND r.administered_at BETWEEN w.week_start_monday AND w.week_end_sunday
--        AND w.is_out_of_district)
--    AND NOT EXISTS (
--      SELECT w.region FROM eligible AS w
--      WHERE w.student_number = r.student_number AND w.academic_year = r.academic_year
--        AND w.region = r.region AND r.administered_at BETWEEN w.week_start_monday AND w.week_end_sunday
--        AND NOT w.is_out_of_district)
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
    types as (
        select
            cast(assessment_id as string) as aid,
            count(distinct coalesce(module_type, '<blank>')) as n_types,
            max(module_type) as module_type,
        from `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup`
        group by 1
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

    -- the enrollment weeks covering the administration, by rpt_tableau__ddi_dashboard's join
    weeks as (
        select
            a.sn,
            a.aid,
            count(w.student_number) as n_weeks,
            logical_or(
                w.is_enrolled_week_end
                and w.enroll_status in (0, 2, 3)
                and not w.is_out_of_district
            ) as any_passes,
            logical_or(w.is_enrolled_week_end) as any_enrolled_week_end,
            logical_or(
                w.is_enrolled_week_end and w.enroll_status in (0, 2, 3)
            ) as any_enrolled_in_status,
            -- the dashboard's IEP status on the week rows that pass its filters
            logical_and(
                case
                    when
                        w.is_enrolled_week_end
                        and w.enroll_status in (0, 2, 3)
                        and not w.is_out_of_district
                    then w.iep_status = 'Has IEP'
                end
            ) as passing_all_has_iep,
        from administrations as a
        left join
            `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks` as w
            on cast(w.student_number as string) = a.sn
            and w.academic_year = a.academic_year
            and w.region = a.region
            and a.administered_at between w.week_start_monday and w.week_end_sunday
        where a.n_administrations = 1
        group by 1, 2
    ),

    -- each student's first enrollment week in the year and region
    first_weeks as (
        select
            cast(student_number as string) as sn,
            academic_year,
            region,
            min(week_start_monday) as first_week_start,
        from `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks`
        group by 1, 2, 3
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
        when t.n_types = 1 and t.module_type = 'WPP'
        then 'C1'
        when t.n_types = 1 and t.module_type is null
        then 'C2'
        -- the comparison is Academic Year 2026; the dashboard joins weeks on
        -- co.academic_year = r.academic_year
        when a.n_administrations = 1 and a.academic_year < 2026
        then 'C3'
        -- no week row covers the date: it falls before the first week
        when k.n_weeks = 0 and a.administered_at < f.first_week_start
        then 'C4'
        when k.n_weeks > 0 and not k.any_passes and not k.any_enrolled_week_end
        then 'C5'
        when k.n_weeks > 0 and not k.any_passes and k.any_enrolled_in_status
        then 'C5O'
        -- Cube's enrollment status says no IEP; the dashboard's week row says
        -- Has IEP, so the row falls in a different IEP scope on each side
        when i.cube_no_iep and k.passing_all_has_iep
        then 'I1'
        else 'UNEXPLAINED'
    end as cause,
from {unmatched} as u
left join types as t on cast(u.source_assessment_id as string) = t.aid
left join
    administrations as a
    on cast(u.lea_student_identifier as string) = a.sn
    and cast(u.source_assessment_id as string) = a.aid
left join
    weeks as k
    on cast(u.lea_student_identifier as string) = k.sn
    and cast(u.source_assessment_id as string) = k.aid
left join
    first_weeks as f
    on a.sn = f.sn
    and a.academic_year = f.academic_year
    and a.region = f.region

left join
    iep_sides as i
    on cast(u.lea_student_identifier as string) = i.sn
    and cast(u.source_assessment_id as string) = i.aid
