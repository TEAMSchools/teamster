-- trunk-ignore-all(sqlfluff)
-- fmt: off
-- cause M1 = dashboard: the student's enrollment changed (grade or school): Cube files the score by the enrollment its resolved section belongs to, the dashboard by the enrollment week it was given in, and the two disagree
-- cause L1 = dashboard: the dashboard labels levels by fixed band numbers (1-2 Below, 3 Approaching, 4-5 At/Above; HS 1 Below, 2 Approaching, 3-5 At/Above; 6 and up unlabeled), so a band set whose mastery band is not 4 (HS: 3) gets a different level than Cube's label relative to the set's mastery band
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
-- reproduce L1:
--  WITH scores AS (
--    SELECT r.academic_year, r.region, r.student_number, r.administered_at, pb.band_number,
--      pb.mastery_band_number, pb.mastery_level
--    FROM `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup` AS r
--    INNER JOIN `teamster-332318`.`kipptaf_assessments`.`int_assessments__performance_band_union` AS pb
--      ON r.source = pb.source AND r.performance_band_set_id = pb.performance_band_set_id
--      AND r.performance_band_label_number = pb.band_number
--    WHERE r.academic_year = 2026 AND r.is_internal_assessment AND r.response_type = 'overall'
--      AND r.module_type != 'WPP' AND pb.is_level_rule_valid),
--  labeled AS (
--    SELECT w.school_level, s.mastery_band_number AS mastery_band, s.mastery_level,
--      CASE
--        WHEN w.school_level = 'HS' THEN CASE s.band_number
--          WHEN 1 THEN 'Below' WHEN 2 THEN 'Approaching'
--          WHEN 3 THEN 'At/Above' WHEN 4 THEN 'At/Above' WHEN 5 THEN 'At/Above' END
--        ELSE CASE s.band_number
--          WHEN 1 THEN 'Below' WHEN 2 THEN 'Below' WHEN 3 THEN 'Approaching'
--          WHEN 4 THEN 'At/Above' WHEN 5 THEN 'At/Above' END
--      END AS dashboard_level
--    FROM scores AS s
--    INNER JOIN `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks` AS w
--      ON w.student_number = s.student_number AND w.academic_year = s.academic_year
--      AND w.region = s.region AND s.administered_at BETWEEN w.week_start_monday AND w.week_end_sunday
--    WHERE w.is_enrolled_week_end AND w.enroll_status IN (0, 2, 3) AND NOT w.is_out_of_district)
--  SELECT school_level, mastery_band, COUNT(*) AS n_rows,
--    COUNTIF(dashboard_level IS DISTINCT FROM mastery_level) AS n_rows_level_differs
--  FROM labeled
--  WHERE (school_level = 'HS' AND mastery_band != 3)
--    OR (school_level != 'HS' AND mastery_band != 4)
--  GROUP BY school_level, mastery_band

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
    ),

    -- int_assessments__performance_band_union: each band set's mastery band
    -- and whether Cube labels it at all (is_level_rule_valid)
    set_rules as (
        select
            source,
            performance_band_set_id,
            count(distinct format('%T|%T', mastery_band_number, is_level_rule_valid)) as n_rules,
            min(mastery_band_number) as mastery_band,
            logical_and(is_level_rule_valid) as is_level_rule_valid,
        from `teamster-332318`.`kipptaf_assessments`.`int_assessments__performance_band_union`
        group by 1, 2
    ),

    -- the band set each assessment's scores read, by the join in
    -- fct_assessment_scores_enrollment_scoped (rr.source, rr.performance_band_set_id),
    -- at the row's grain: assessment and response type
    band_sets as (
        select
            cast(rr.assessment_id as string) as aid,
            coalesce(rr.response_type, 'not_taken') as response_type,
            count(distinct format('%T|%T', rr.source, rr.performance_band_set_id)) as n_sets,
            logical_and(sr.n_rules = 1) as is_one_rule,
            min(sr.mastery_band) as mastery_band,
            logical_and(sr.is_level_rule_valid) as is_level_rule_valid,
        from `teamster-332318`.`kipptaf_assessments`.`int_assessments__response_rollup` as rr
        left join
            set_rules as sr
            on rr.source = sr.source
            and rr.performance_band_set_id = sr.performance_band_set_id
        where rr.is_internal_assessment
        group by 1, 2
    ),

    -- the school_level the workbook calc reads, per school, from the enrollment
    -- weeks rpt_tableau__ddi_dashboard keeps; the comparison is Academic Year 2026
    school_levels as (
        select
            school,
            count(distinct school_level) as n_levels,
            min(school_level) as school_level,
        from `teamster-332318`.`kipptaf_extracts`.`int_extracts__student_enrollments_weeks`
        where
            academic_year = 2026
            and is_enrolled_week_end
            and enroll_status in (0, 2, 3)
            and not is_out_of_district
        group by 1
    )

select
    u.__row,
    case
        when
            c.n_cells = 1
            and d.n_cells = 1
            and (c.grade_level != d.grade_level or c.school != d.school)
        then 'M1'
        -- Cube: band_number >= mastery_band_number is At/Above, one below
        -- Approaching. The workbook calc: school_level = 'HS' puts At/Above at
        -- band 3, Approaching at 2; any other school at band 4 and 3.
        when
            b.n_sets = 1
            and b.is_one_rule
            and b.is_level_rule_valid
            and s.n_levels = 1
            and (
                (s.school_level = 'HS' and b.mastery_band != 3)
                or (s.school_level != 'HS' and b.mastery_band != 4)
            )
        then 'L1'
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
left join
    band_sets as b
    on cast(u.source_assessment_id as string) = b.aid
    and u.response_type = b.response_type
left join school_levels as s on u.abbreviation = s.school
