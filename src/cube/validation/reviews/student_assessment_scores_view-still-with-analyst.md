# Still with the analyst: `student_assessment_scores_view`

The open items behind the review issue's counts, not explained yet. Row and cell
counts under 10 show as `<10`, and a total beside a hidden count as a bound; an
item under 10 rows or cells is not listed.

## `pct_proficient__dki_grid` in `student_assessment_scores_view` (cube_only)

- Fewer than 10 more items, each under 10 rows or cells, are not listed.

## `pct_proficient__dki_grid` in `student_assessment_scores_view` (dims_differ)

- Fewer than 10 more items, each under 10 rows or cells, are not listed.

## `pct_proficient__dki_standards_grid` in `student_assessment_scores_view` (cube_only)

- Under 10 rows or cells each, not listed: 29 items.

## `pct_proficient__dki_standards_grid` in `student_assessment_scores_view` (dims_differ)

- Fewer than 10 more items, each under 10 rows or cells, are not listed.

## `grade_goal_distance__grid_grade` in `student_assessment_scores_view` (cube_only)

- `grade_goal_distance__grid_grade:school_week_start_date=<redacted>,grade_level=3,academic_subject=Text Study`,
  masked rows; a trace lead; ask the analyst
- Fewer than 10 more items, each under 10 rows or cells, are not listed.

## `grade_goal_distance__grid_grade` in `student_assessment_scores_view` (dims_differ)

- Fewer than 10 more items, each under 10 rows or cells, are not listed.

## `school_goal_distance__lines_all` in `student_assessment_scores_view` (cube_only)

- `school_goal_distance__lines_all:school_week_start_date=<redacted>,abbreviation=SPARK#4`,
  33 rows; a trace lead; ask the analyst
- `school_goal_distance__lines_all:school_week_start_date=<redacted>,abbreviation=THRIVE#4`,
  masked rows; a trace lead; ask the analyst
- `school_goal_distance__lines_all:school_week_start_date=<redacted>,abbreviation=Life#6`,
  179 rows; a trace lead; ask the analyst
- Fewer than 10 more items, each under 10 rows or cells, are not listed.

## `school_goal_distance__lines_all` in `student_assessment_scores_view` (dims_differ)

- Fewer than 10 more items, each under 10 rows or cells, are not listed.

## `region_goal_distance__lines_all` in `student_assessment_scores_view` (cube_only)

- `region_goal_distance__lines_all:school_week_start_date=<redacted>,region_name=Newark#4`,
  327 rows; a trace lead; ask the analyst
- `region_goal_distance__lines_all:school_week_start_date=<redacted>,region_name=Newark#7`,
  918 rows; a trace lead; ask the analyst
- `region_goal_distance__lines_all:school_week_start_date=<redacted>,region_name=Newark#11`,
  1063 rows; a trace lead; ask the analyst
- `region_goal_distance__lines_all:school_week_start_date=<redacted>,region_name=Newark#18`,
  21 rows; a trace lead; ask the analyst

## `pct_taken__assessments_over_time` in `student_assessment_scores_view` (dims_differ)

- `pct_taken__assessments_over_time:module_type=<redacted>,module_code=<redacted>,grade_level=<redacted>,d:module_type=<redacted>,d:module_code=<redacted>,d:grade_level=<redacted>#10`,
  masked rows; a trace lead; ask the analyst
- Under 10 rows or cells each, not listed: 13 items.

## `pct_students_at_level__dki_bars` in `student_assessment_scores_view` (cube_only)

- Fewer than 10 more items, each under 10 rows or cells, are not listed.

## `pct_students_at_level__dki_bars` in `student_assessment_scores_view` (dims_differ)

- Fewer than 10 more items, each under 10 rows or cells, are not listed.

## `pct_students_at_level__dki_standards_bars` in `student_assessment_scores_view` (cube_only)

- Under 10 rows or cells each, not listed: 30 items.

## `pct_students_at_level__dki_standards_bars` in `student_assessment_scores_view` (dims_differ)

- Fewer than 10 more items, each under 10 rows or cells, are not listed.

## `pct_proficient__dki_grid` in `student_assessment_scores_view` (cells)

- `pct_proficient__dki_grid:cells`, 1406 cells; a trace lead; ask the analyst

## `pct_proficient__dki_standards_grid` in `student_assessment_scores_view` (cells)

- `pct_proficient__dki_standards_grid:cells`, 724 cells; a trace lead; ask the
  analyst

## `grade_goal_distance__grid_grade` in `student_assessment_scores_view` (cells)

- `grade_goal_distance__grid_grade:cells`, 37 cells; a trace lead; ask the
  analyst

## `school_goal_distance__lines_all` in `student_assessment_scores_view` (cells)

- `school_goal_distance__lines_all:cells`, 106 cells; a trace lead; ask the
  analyst

## `region_goal_distance__lines_all` in `student_assessment_scores_view` (cells)

- `region_goal_distance__lines_all:cells`, 29 cells; a trace lead; ask the
  analyst

## `pct_students_at_level__dki_bars` in `student_assessment_scores_view` (cells)

- `pct_students_at_level__dki_bars:cells`, 823 cells; a trace lead; ask the
  analyst

## `pct_students_at_level__dki_standards_bars` in `student_assessment_scores_view` (cells)

- `pct_students_at_level__dki_standards_bars:cells`, 2973 cells; a trace lead;
  ask the analyst
