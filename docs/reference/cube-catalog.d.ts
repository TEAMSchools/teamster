/**
 * Cube semantic layer -- generated TypeScript surface.
 *
 * GENERATED FILE -- do not edit by hand.
 * Regenerate with `uv run scripts/cube_types_export.py`.
 *
 * Source: docs/reference/cube-catalog-meta.json (Cube Cloud production deployment).
 * 6 views, 40 measures, 295 dimensions.
 *
 * Query the REST API at `POST {baseUrl}/cubejs-api/v1/load` with a JSON body
 * `{ query: CubeQuery<V> }`. The `Authorization` header takes the RAW token
 * with no `Bearer` prefix.
 *
 * Two response behaviours these types encode deliberately:
 *
 * - Numeric measures come back as JSON STRINGS (`"900"`, not `900`), so
 *   `MeasureValue` is `string`. Parse before doing arithmetic.
 * - Every member is optional on a row, because a row carries only the members
 *   the query requested, and any of them can be null.
 *
 * One behaviour they cannot encode: an `access_policy` denial blocks the WHOLE
 * query rather than stripping the member you are not entitled to. A query that
 * type-checks can still 403 for a viewer with a narrower scope. Build for that.
 */

/** Granularities accepted on a `timeDimensions` entry. */
export type Granularity =
  "second" | "minute" | "hour" | "day" | "week" | "month" | "quarter" | "year";

/**
 * Numeric measures are serialised as strings by the REST API. Parse with
 * `Number(...)` before arithmetic; do not assume `number`.
 */
export type MeasureValue = string;

/** Time dimensions are serialised as ISO 8601 strings. */
export type TimeDimensionValue = string;

/**
 * Numeric dimensions. Typed permissively: measure stringification is verified,
 * but whether numeric DIMENSIONS are stringified is not, so narrow at the edge
 * rather than trusting one branch of this union.
 */
export type NumericDimensionValue = string | number;

/** Filter operators accepted on a `filters` entry. */
export type FilterOperator =
  | "equals"
  | "notEquals"
  | "contains"
  | "notContains"
  | "startsWith"
  | "endsWith"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "set"
  | "notSet"
  | "inDateRange"
  | "notInDateRange"
  | "beforeDate"
  | "afterDate";

/** Staff Directory -- Open staff directory — roster, employment history, and work-contact info. One row per employee x employment period — a contiguous window during which status, job, worker type, org unit, and location all held simultaneously — with point-in-time manager context. Use for the staff roster, drill-down, and individual investigations. Contains no personal or sensitive data (personal contact, DOB, demographics) — see staff_pii for those fields. Always apply a date filter. Without one, each employment period fans out to one row per calendar day in its effective range. For a current roster, filter dates to today; for headcount over time, filter a date range or month-ends. Filter is_primary_position = true to count each person once; status_name = 'Active' filters to active employees (excludes Leave). Use count_employees (count_distinct on staff_key) for headcounts. */
export type StaffDirectoryMeasure = "staff_directory.count_employees";

export type StaffDirectoryDimension =
  | "staff_directory.status_name"
  | "staff_directory.status_reason"
  | "staff_directory.position_title"
  | "staff_directory.job_code"
  | "staff_directory.worker_type"
  | "staff_directory.department_name"
  | "staff_directory.business_unit_name"
  | "staff_directory.is_primary_position"
  | "staff_directory.is_management_position"
  | "staff_directory.full_time_equivalency"
  | "staff_directory.effective_start_date"
  | "staff_directory.dates_date_day"
  | "staff_directory.dates_academic_year"
  | "staff_directory.dates_month_name"
  | "staff_directory.dates_month_number"
  | "staff_directory.dates_year_number"
  | "staff_directory.staff_key"
  | "staff_directory.staff_unique_id"
  | "staff_directory.full_name"
  | "staff_directory.first_name"
  | "staff_directory.last_name"
  | "staff_directory.work_email"
  | "staff_directory.google_email"
  | "staff_directory.active_directory_username"
  | "staff_directory.original_hire_date"
  | "staff_directory.rehire_date"
  | "staff_directory.job_function_level"
  | "staff_directory.job_function_code"
  | "staff_directory.department_group"
  | "staff_directory.locations_location_name"
  | "staff_directory.locations_abbreviation"
  | "staff_directory.locations_grade_band"
  | "staff_directory.locations_campus"
  | "staff_directory.locations_city"
  | "staff_directory.regions_region_name"
  | "staff_directory.regions_state"
  | "staff_directory.staff_manager_staff_key"
  | "staff_directory.staff_manager_full_name"
  | "staff_directory.staff_manager_first_name"
  | "staff_directory.staff_manager_last_name"
  | "staff_directory.staff_manager_work_email";

export type StaffDirectoryTimeDimension =
  | "staff_directory.effective_start_date"
  | "staff_directory.dates_date_day"
  | "staff_directory.original_hire_date"
  | "staff_directory.rehire_date";

export type StaffDirectoryMember =
  StaffDirectoryMeasure | StaffDirectoryDimension;

/** A `/load` row from `staff_directory`. */
export interface StaffDirectoryRow {
  /** Count Employees -- Distinct employees in scope. Counts a person once even with multiple concurrent assignments. Filter is_primary_position = true to count the primary assignment only. Always apply a date filter. */
  "staff_directory.count_employees"?: MeasureValue | null;
  /** Status Name -- Assignment-level employment status during this period (Active, Leave, Terminated). Sourced from dim_work_assignment_status (ADP assignmentStatus), which is more granular than the worker-level status and has a populated name. Filter status_name = 'Active' for active headcount (excludes Leave). */
  "staff_directory.status_name"?: string | null;
  /** Status Reason -- Reason for the current status (e.g., leave type — Medical, Family, Disability; or termination reason — Resignation, Non-Renewal). Null for many Active periods. */
  "staff_directory.status_reason"?: string | null;
  /** Position Title -- Free-text position title for the work assignment, as held during this period. */
  "staff_directory.position_title"?: string | null;
  /** Job Code -- Job code value for the work assignment, as held during this period. */
  "staff_directory.job_code"?: string | null;
  /** Worker Type -- Display name for the ADP worker type (e.g., Regular, Temporary), as held during this period. */
  "staff_directory.worker_type"?: string | null;
  /** Department Name -- Display name for the home Department, coalesced from longName and shortName of the ADP nameCode where typeCode = 'Department', as held during this period. */
  "staff_directory.department_name"?: string | null;
  /** Business Unit Name -- Display name for the home Business Unit, coalesced from longName and shortName of the ADP nameCode where typeCode = 'Business Unit', as held during this period. */
  "staff_directory.business_unit_name"?: string | null;
  /** Is Primary Position -- TRUE if this was the worker's primary work assignment during the period. A worker may have multiple concurrent assignments; at most one is primary at any moment. Filter to true to count each person once. */
  "staff_directory.is_primary_position"?: boolean | null;
  /** Is Management Position -- TRUE if this work assignment is designated as a management position. */
  "staff_directory.is_management_position"?: boolean | null;
  /** Full Time Equivalency -- FTE ratio for this work assignment. 1.0 represents full-time; fractional values represent part-time assignments. */
  "staff_directory.full_time_equivalency"?: NumericDimensionValue | null;
  /** Effective Start Date -- Start of the contiguous period (intersection of all SCD2 children). */
  "staff_directory.effective_start_date"?: TimeDimensionValue | null;
  /** Dates Date Day -- Timestamp cast of date_key. Required by Cube for date dimension joins. */
  "staff_directory.dates_date_day"?: TimeDimensionValue | null;
  /** Dates Academic Year -- KIPP academic year (July start). The calendar year in which the academic year begins (e.g., 2025 for the 2025-26 school year). For filtering by year, prefer academic_year_label (the unambiguous "2025-2026" string form) over this integer. */
  "staff_directory.dates_academic_year"?: NumericDimensionValue | null;
  /** Dates Month Name -- Full month name (January, February, etc.). */
  "staff_directory.dates_month_name"?: string | null;
  /** Dates Month Number -- Month number (1-12). */
  "staff_directory.dates_month_number"?: NumericDimensionValue | null;
  /** Dates Year Number -- Calendar year. */
  "staff_directory.dates_year_number"?: NumericDimensionValue | null;
  /** Staff Key -- Surrogate key derived from employee_number. Primary key for the staff dimension and the FK target for staff-to-student bridging. */
  "staff_directory.staff_key"?: string | null;
  /** Staff Unique ID -- KIPP-assigned unique identifier for all staff members across all entities. */
  "staff_directory.staff_unique_id"?: NumericDimensionValue | null;
  /** Full Name -- Staff member's preferred name in Last, First Middle format. */
  "staff_directory.full_name"?: string | null;
  /** First Name -- Staff member's preferred first name. */
  "staff_directory.first_name"?: string | null;
  /** Last Name -- Staff member's preferred last name. */
  "staff_directory.last_name"?: string | null;
  /** Work Email -- Staff member's work email address from ADP. */
  "staff_directory.work_email"?: string | null;
  /** Google Email -- Staff member's Google Workspace email address from LDAP. */
  "staff_directory.google_email"?: string | null;
  /** Active Directory Username -- Staff member's Active Directory username (lowercased), used as a cross-system identifier. */
  "staff_directory.active_directory_username"?: string | null;
  /** Original Hire Date -- The date the staff member was originally hired at KIPP, from worker_dates in ADP. */
  "staff_directory.original_hire_date"?: TimeDimensionValue | null;
  /** Rehire Date -- The most recent rehire date for the staff member, if rehired, from worker_dates in ADP. */
  "staff_directory.rehire_date"?: TimeDimensionValue | null;
  /** Job Function Level -- Numeric seniority level for the staff member's current job function (higher = more senior). Used by the staff_pii reporting_chain_or_below_rank scope: viewers see staff with a level numerically greater than their own. */
  "staff_directory.job_function_level"?: NumericDimensionValue | null;
  /** Job Function Code -- Short code for the staff member's current job function category (e.g. TEACH, TIR). Used by the staff_pii teaching_staff scope to restrict access to classroom teachers and teacher-in-residence. */
  "staff_directory.job_function_code"?: string | null;
  /** Department Group -- Broad department grouping for the staff member's current role (e.g. Academics, Ops). Department axis of the shared staff sensitive remit (staff_department_scope = own_group). */
  "staff_directory.department_group"?: string | null;
  /** Locations Location Name -- Canonical location name. */
  "staff_directory.locations_location_name"?: string | null;
  /** Locations Abbreviation -- Short display name for the location. */
  "staff_directory.locations_abbreviation"?: string | null;
  /** Locations Grade Band -- Grade band served (ES, MS, HS). */
  "staff_directory.locations_grade_band"?: string | null;
  /** Locations Campus -- Physical campus name. Multiple schools may share a campus. */
  "staff_directory.locations_campus"?: string | null;
  /** Locations City -- City. Nullable for non-physical rows (e.g., campus rollups). */
  "staff_directory.locations_city"?: string | null;
  /** Regions Region Name -- Region name (Camden, Miami, Newark, Paterson, TAF). */
  "staff_directory.regions_region_name"?: string | null;
  /** Regions State -- US state (NJ or FL). */
  "staff_directory.regions_state"?: string | null;
  /** Staff Manager Staff Key -- Surrogate key derived from employee_number. Primary key for the staff dimension and the FK target for staff-to-student bridging. */
  "staff_directory.staff_manager_staff_key"?: string | null;
  /** Staff Manager Full Name -- Staff member's preferred name in Last, First Middle format. */
  "staff_directory.staff_manager_full_name"?: string | null;
  /** Staff Manager First Name -- Staff member's preferred first name. */
  "staff_directory.staff_manager_first_name"?: string | null;
  /** Staff Manager Last Name -- Staff member's preferred last name. */
  "staff_directory.staff_manager_last_name"?: string | null;
  /** Staff Manager Work Email -- Staff member's work email address from ADP. */
  "staff_directory.staff_manager_work_email"?: string | null;
}

/** Staff Pii -- Sensitive staff PII — personal contact info, date of birth, and demographics — split out of the open staff directory (see staff_directory). One row per employee x employment period; always apply a date filter or each period fans out to one row per calendar day in its effective range. Filter is_primary_position = true and status_name = 'Active' to see each current employee once. Row-level access is remit-scoped: a viewer only sees rows for staff within their location/department remit (added in Task 5's row_level policy). job_function_level, job_function_code, and department_group are exposed here because the remit filter matches on them; abbreviation and region_key are exposed because the remit filter also scopes by location. Those three role attributes are the viewed staff member's CURRENT role (from dim_staff_cube_access), not the value per historical period — so the remit gate is person-level, not period-accurate. */
export type StaffPiiMeasure = "staff_pii.count_employees";

export type StaffPiiDimension =
  | "staff_pii.is_primary_position"
  | "staff_pii.status_name"
  | "staff_pii.dates_date_day"
  | "staff_pii.dates_academic_year"
  | "staff_pii.staff_key"
  | "staff_pii.full_name"
  | "staff_pii.personal_email"
  | "staff_pii.personal_cell_phone"
  | "staff_pii.birth_date"
  | "staff_pii.gender_identity"
  | "staff_pii.race"
  | "staff_pii.is_hispanic"
  | "staff_pii.job_function_level"
  | "staff_pii.job_function_code"
  | "staff_pii.department_group"
  | "staff_pii.locations_abbreviation"
  | "staff_pii.locations_region_key";

export type StaffPiiTimeDimension =
  "staff_pii.dates_date_day" | "staff_pii.birth_date";

export type StaffPiiMember = StaffPiiMeasure | StaffPiiDimension;

/** A `/load` row from `staff_pii`. */
export interface StaffPiiRow {
  /** Count Employees -- Distinct employees in scope. Counts a person once even with multiple concurrent assignments. Filter is_primary_position = true to count the primary assignment only. Always apply a date filter. */
  "staff_pii.count_employees"?: MeasureValue | null;
  /** Is Primary Position -- TRUE if this was the worker's primary work assignment during the period. A worker may have multiple concurrent assignments; at most one is primary at any moment. Filter to true to count each person once. */
  "staff_pii.is_primary_position"?: boolean | null;
  /** Status Name -- Assignment-level employment status during this period (Active, Leave, Terminated). Sourced from dim_work_assignment_status (ADP assignmentStatus), which is more granular than the worker-level status and has a populated name. Filter status_name = 'Active' for active headcount (excludes Leave). */
  "staff_pii.status_name"?: string | null;
  /** Dates Date Day -- Timestamp cast of date_key. Required by Cube for date dimension joins. */
  "staff_pii.dates_date_day"?: TimeDimensionValue | null;
  /** Dates Academic Year -- KIPP academic year (July start). The calendar year in which the academic year begins (e.g., 2025 for the 2025-26 school year). For filtering by year, prefer academic_year_label (the unambiguous "2025-2026" string form) over this integer. */
  "staff_pii.dates_academic_year"?: NumericDimensionValue | null;
  /** Staff Key -- Surrogate key derived from employee_number. Primary key for the staff dimension and the FK target for staff-to-student bridging. */
  "staff_pii.staff_key"?: string | null;
  /** Full Name -- Staff member's preferred name in Last, First Middle format. */
  "staff_pii.full_name"?: string | null;
  /** Personal Email -- Staff member's personal email address from ADP. */
  "staff_pii.personal_email"?: string | null;
  /** Personal Cell Phone -- Staff member's personal cell phone number from ADP. */
  "staff_pii.personal_cell_phone"?: string | null;
  /** Birth Date -- Staff member's date of birth. */
  "staff_pii.birth_date"?: TimeDimensionValue | null;
  /** Gender Identity -- Staff member's preferred gender identity as reported in the staff information survey, with ADP gender_code as fallback. */
  "staff_pii.gender_identity"?: string | null;
  /** Race -- Staff member's racial category for reporting purposes, sourced from the staff information survey with ADP as fallback. */
  "staff_pii.race"?: string | null;
  /** Is Hispanic -- TRUE if the staff member identified as Hispanic/Latino/Latinx in the staff information survey or ADP ethnicity record. */
  "staff_pii.is_hispanic"?: boolean | null;
  /** Job Function Level -- Numeric seniority level for the staff member's current job function (higher = more senior). Used by the staff_pii reporting_chain_or_below_rank scope: viewers see staff with a level numerically greater than their own. */
  "staff_pii.job_function_level"?: NumericDimensionValue | null;
  /** Job Function Code -- Short code for the staff member's current job function category (e.g. TEACH, TIR). Used by the staff_pii teaching_staff scope to restrict access to classroom teachers and teacher-in-residence. */
  "staff_pii.job_function_code"?: string | null;
  /** Department Group -- Broad department grouping for the staff member's current role (e.g. Academics, Ops). Department axis of the shared staff sensitive remit (staff_department_scope = own_group). */
  "staff_pii.department_group"?: string | null;
  /** Locations Abbreviation -- Short display name for the location. */
  "staff_pii.locations_abbreviation"?: string | null;
  /** Locations Region Key -- Foreign key to regions. Surrogate key derived from `business_unit_code` so this column hashes exactly the keys produced by `regions.region_key`. Network-level locations (e.g., KIPP NJ) map to KIPP_TAF. */
  "staff_pii.locations_region_key"?: string | null;
}

/** Student Assessment Scores View -- Assessment scores across internal Illuminate interims, NJ/FL state assessments, and vendor benchmarks (i-Ready, DIBELS, STAR) — row-level (one row per student x assessment x administration x response type) and aggregate breakdowns in a single view. pct_proficient (mastery rate) is the source-agnostic headline; scale_score is null for internal rows and percent_correct is null for state and vendor rows. response_type / response_type_code carry the standard/skill breakdown (Illuminate only). State and vendor administrations have no single administered date, so the Date members (academic_year, academic_year_label, date_day, month_number, month_name) resolve for every source but are scoped by different dates per source: the administration date for Illuminate/college, the student's completion (test) date for state/vendor. A cross-source date cut (e.g. "scores in May") therefore mixes those two date concepts. Contains direct student identifiers — see access_policy for PII gating. */
export type StudentAssessmentScoresViewMeasure =
  | "student_assessment_scores_view.count_scores"
  | "student_assessment_scores_view.count_students"
  | "student_assessment_scores_view.pct_proficient"
  | "student_assessment_scores_view.pct_proficient_formative"
  | "student_assessment_scores_view.pct_proficient_crq"
  | "student_assessment_scores_view.avg_percent_correct"
  | "student_assessment_scores_view.avg_scale_score";

export type StudentAssessmentScoresViewDimension =
  | "student_assessment_scores_view.assessment_score_key"
  | "student_assessment_scores_view.date_taken"
  | "student_assessment_scores_view.enrollment_resolution"
  | "student_assessment_scores_view.proficiency_level"
  | "student_assessment_scores_view.performance_band_label_number"
  | "student_assessment_scores_view.is_mastery"
  | "student_assessment_scores_view.scale_score"
  | "student_assessment_scores_view.percent_correct"
  | "student_assessment_scores_view.response_type"
  | "student_assessment_scores_view.response_type_code"
  | "student_assessment_scores_view.response_type_description"
  | "student_assessment_scores_view.response_type_root_description"
  | "student_assessment_scores_view.is_replacement"
  | "student_assessment_scores_view.title"
  | "student_assessment_scores_view.academic_subject"
  | "student_assessment_scores_view.assessment_type"
  | "student_assessment_scores_view.category"
  | "student_assessment_scores_view.module_code"
  | "student_assessment_scores_view.module_type"
  | "student_assessment_scores_view.grade_level_tested"
  | "student_assessment_scores_view.scope"
  | "student_assessment_scores_view.is_internal_assessment"
  | "student_assessment_scores_view.administration_period"
  | "student_assessment_scores_view.test_type"
  | "student_assessment_scores_view.source_assessment_id"
  | "student_assessment_scores_view.date_day"
  | "student_assessment_scores_view.academic_year"
  | "student_assessment_scores_view.academic_year_label"
  | "student_assessment_scores_view.month_number"
  | "student_assessment_scores_view.month_name"
  | "student_assessment_scores_view.discipline"
  | "student_assessment_scores_view.course_title"
  | "student_assessment_scores_view.course_code"
  | "student_assessment_scores_view.credit_type"
  | "student_assessment_scores_view.is_foundations"
  | "student_assessment_scores_view.identifier"
  | "student_assessment_scores_view.period"
  | "student_assessment_scores_view.student_section_enrollment_key"
  | "student_assessment_scores_view.student_enrollment_key"
  | "student_assessment_scores_view.entry_date"
  | "student_assessment_scores_view.exit_date"
  | "student_assessment_scores_view.is_dropped_section"
  | "student_assessment_scores_view.is_dropped_course"
  | "student_assessment_scores_view.lead_teacher_staff_key"
  | "student_assessment_scores_view.staff_lead_teacher_full_name"
  | "student_assessment_scores_view.staff_lead_teacher_first_name"
  | "student_assessment_scores_view.staff_lead_teacher_last_name"
  | "student_assessment_scores_view.grade_level"
  | "student_assessment_scores_view.graduation_year"
  | "student_assessment_scores_view.year_in_network"
  | "student_assessment_scores_view.is_retained_year"
  | "student_assessment_scores_view.is_ell"
  | "student_assessment_scores_view.is_iep"
  | "student_assessment_scores_view.iep_classification"
  | "student_assessment_scores_view.special_education_code"
  | "student_assessment_scores_view.special_education_name"
  | "student_assessment_scores_view.special_education_placement"
  | "student_assessment_scores_view.is_meal_eligible"
  | "student_assessment_scores_view.meal_eligibility"
  | "student_assessment_scores_view.student_key"
  | "student_assessment_scores_view.full_name"
  | "student_assessment_scores_view.birth_date"
  | "student_assessment_scores_view.lea_student_identifier"
  | "student_assessment_scores_view.state_student_identifier"
  | "student_assessment_scores_view.district_student_identifier"
  | "student_assessment_scores_view.salesforce_contact_id"
  | "student_assessment_scores_view.gender_identity"
  | "student_assessment_scores_view.race"
  | "student_assessment_scores_view.enrollment_status"
  | "student_assessment_scores_view.is_gifted"
  | "student_assessment_scores_view.location_name"
  | "student_assessment_scores_view.abbreviation"
  | "student_assessment_scores_view.region_key"
  | "student_assessment_scores_view.grade_band"
  | "student_assessment_scores_view.campus"
  | "student_assessment_scores_view.city"
  | "student_assessment_scores_view.region_name"
  | "student_assessment_scores_view.state"
  | "student_assessment_scores_view.semester"
  | "student_assessment_scores_view.term_name"
  | "student_assessment_scores_view.term_code"
  | "student_assessment_scores_view.term_type";

export type StudentAssessmentScoresViewTimeDimension =
  | "student_assessment_scores_view.date_taken"
  | "student_assessment_scores_view.date_day"
  | "student_assessment_scores_view.entry_date"
  | "student_assessment_scores_view.exit_date"
  | "student_assessment_scores_view.birth_date";

export type StudentAssessmentScoresViewMember =
  StudentAssessmentScoresViewMeasure | StudentAssessmentScoresViewDimension;

/** A `/load` row from `student_assessment_scores_view`. */
export interface StudentAssessmentScoresViewRow {
  /** Count Scores -- Scored-response count. COUNT(*) over the unique PK (assessment_score_key) — additive, so pre-aggregations roll it up to any grain. */
  "student_assessment_scores_view.count_scores"?: MeasureValue | null;
  /** Count Students -- Distinct students (per student-year) with a score in the filtered slice. Exact count_distinct — non-additive, so a rollup pre-aggregation cannot re-aggregate it to a coarser grain; switch to count_distinct_approx (HLL) if/when this is pre-aggregated and an approximate distinct is acceptable. */
  "student_assessment_scores_view.count_students"?: MeasureValue | null;
  /** Pct Proficient -- Proficiency/mastery rate — proficient scores / total scores. The headline, source-agnostic metric (the only score measure comparable across the incompatible scales of internal vs state assessments). Built from additive primitives (_sum_proficient / count_scores) so pre-aggregations roll it up to any grain. */
  "student_assessment_scores_view.pct_proficient"?: MeasureValue | null;
  /** Pct Proficient Formative -- Proficiency rate across all formative module types (Quick Assessments, Multiple-Choice Quick Questions, and Constructed Response Questions). CRQ is included and also available as the standalone pct_proficient_crq measure. Built from additive primitives so pre-aggregations roll it up. */
  "student_assessment_scores_view.pct_proficient_formative"?: MeasureValue | null;
  /** Pct Proficient Crq -- Proficiency rate for Constructed Response Questions (CRQ) across all regions. CRQ is a subset of pct_proficient_formative. Built from additive primitives so pre-aggregations roll it up. */
  "student_assessment_scores_view.pct_proficient_crq"?: MeasureValue | null;
  /** Avg Percent Correct -- Grain: recomputes at any query grain, but meaningful only within a single subject/standard — pooling percent-correct across assessments is a silent-failure trap (numerically valid, semantically meaningless). Average percent correct, internal-effective (null for state), built from additive primitives so pre-aggregations roll it up. */
  "student_assessment_scores_view.avg_percent_correct"?: MeasureValue | null;
  /** Avg Scale Score -- Grain: recomputes at any query grain, but meaningful only within a single assessment source/subject/grade — scale scores are not comparable across sources, so pooling them is a silent-failure trap (numerically valid, semantically meaningless). Average scale score, built from additive primitives so pre-aggregations roll it up. */
  "student_assessment_scores_view.avg_scale_score"?: MeasureValue | null;
  /** Assessment Score Key -- Surrogate key. Primary key for this fact. */
  "student_assessment_scores_view.assessment_score_key"?: string | null;
  /** Date Taken -- Date the assessment was taken (completion date), as a standalone date dimension not joined to a calendar cube. date_taken is corrupt for a small share of internal rows, so calendar and academic-year rollups use the date_day / academic_year members instead (backed by assessment_date_key: the administration date for internal and college, the reliable test date for state and vendor). Populated for state and vendor rows; nullable for a small share of internal rows lacking a recorded sitting. */
  "student_assessment_scores_view.date_taken"?: TimeDimensionValue | null;
  /** Enrollment Resolution -- How the section enrollment was resolved: subject_section or homeroom. Filter to subject_section for course/section-level rollups. */
  "student_assessment_scores_view.enrollment_resolution"?: string | null;
  /** Proficiency Level -- Proficiency band label (performance band for internal, achievement level for state). */
  "student_assessment_scores_view.proficiency_level"?: string | null;
  /** Performance Band Label Number -- Numeric ordering of the performance band label within the band scale. Null for state assessments. */
  "student_assessment_scores_view.performance_band_label_number"?: NumericDimensionValue | null;
  /** Is Mastery -- TRUE if the student met the mastery/proficiency threshold for this assessment. */
  "student_assessment_scores_view.is_mastery"?: boolean | null;
  /** Scale Score -- Scale score achieved. Null for internal (percent-correct) rows. */
  "student_assessment_scores_view.scale_score"?: NumericDimensionValue | null;
  /** Percent Correct -- Percent correct. Null for state assessments. */
  "student_assessment_scores_view.percent_correct"?: NumericDimensionValue | null;
  /** Response Type -- Response-type breakdown (e.g., overall, strand, standard). Null for state assessments. */
  "student_assessment_scores_view.response_type"?: string | null;
  /** Response Type Code -- Short code identifying the response type. Null for state. */
  "student_assessment_scores_view.response_type_code"?: string | null;
  /** Response Type Description -- Human-readable response-type description. Null for state. */
  "student_assessment_scores_view.response_type_description"?: string | null;
  /** Response Type Root Description -- Description of the root (top-level) response type. Null for state. */
  "student_assessment_scores_view.response_type_root_description"?:
    string | null;
  /** Is Replacement -- Illuminate-only flag. TRUE when a K-8 student sat a replacement-curriculum assessment off their enrolled grade level. Null for all non-Illuminate sources (state and vendor: iReady, DIBELS, STAR), which have no replacement-curriculum concept. */
  "student_assessment_scores_view.is_replacement"?: boolean | null;
  /** Title -- Display name of the assessment. */
  "student_assessment_scores_view.title"?: string | null;
  /** Academic Subject -- Subject tested (e.g., Mathematics, English Language Arts, Reading, Science). */
  "student_assessment_scores_view.academic_subject"?: string | null;
  /** Assessment Type -- Source-system category. Values that currently carry scores on the assessment-scores view: illuminate (internal interims), iready, dibels, star, and the state assessments state_nj_njsla, state_nj_njsla_science, state_nj_njgpa, state_fl_fast, state_fl_science, state_fl_eoc. Other categories exist upstream (college, ap, state_nj_parcc, state_fl_fsa, plus _unknown fallbacks) but carry no scores on this view today; treat this list as current, not closed. */
  "student_assessment_scores_view.assessment_type"?: string | null;
  /** Category -- Assessment category by format/content (e.g., CMA, CGI, NJSLA, FAST, SAT). */
  "student_assessment_scores_view.category"?: string | null;
  /** Module Code -- Module/test code identifying the assessment variant (e.g., QA1, ELA05, sat_total_score). */
  "student_assessment_scores_view.module_code"?: string | null;
  /** Module Type -- Module type for internal Illuminate assessments (e.g., QA, CR). Null for state and college. */
  "student_assessment_scores_view.module_type"?: string | null;
  /** Grade Level Tested -- Grade level the assessment targets. Null for college-entrance assessments. */
  "student_assessment_scores_view.grade_level_tested"?: NumericDimensionValue | null;
  /** Scope -- How scores link to students: enrollment (tied to a section enrollment) or student. */
  "student_assessment_scores_view.scope"?: string | null;
  /** Is Internal Assessment -- TRUE for KIPP-created internal assessments via Illuminate; FALSE for state and college. */
  "student_assessment_scores_view.is_internal_assessment"?: boolean | null;
  /** Administration Period -- Scheduling period distinguishing administrations within an academic year. NJ state: testing season (Fall, Winter, Spring). FL state: FLDOE window. College: College Board round. Null for Illuminate and AP. */
  "student_assessment_scores_view.administration_period"?: string | null;
  /** Test Type -- Official vs Practice for college-entrance administrations. Null for Illuminate, state, and AP. */
  "student_assessment_scores_view.test_type"?: string | null;
  /** Source Assessment ID -- Illuminate assessment id carried to the administration grain (the canonical id). Null for non-Illuminate branches. */
  "student_assessment_scores_view.source_assessment_id"?: NumericDimensionValue | null;
  /** Date Day -- Timestamp cast of date_key. Required by Cube for date dimension joins. */
  "student_assessment_scores_view.date_day"?: TimeDimensionValue | null;
  /** Academic Year -- KIPP academic year (July start). The calendar year in which the academic year begins (e.g., 2025 for the 2025-26 school year). For filtering by year, prefer academic_year_label (the unambiguous "2025-2026" string form) over this integer. */
  "student_assessment_scores_view.academic_year"?: NumericDimensionValue | null;
  /** Academic Year Label -- Full span label for the academic year (e.g. "2025-2026" for the year beginning July 2025). Use this as the canonical filter surface when querying by year — it is unambiguous regardless of SY vs. start-year notation. academic_year 2025 = academic_year_label "2025-2026" = SY26. The integer academic_year is retained for sort/group/math only. */
  "student_assessment_scores_view.academic_year_label"?: string | null;
  /** Month Number -- Month number (1-12). */
  "student_assessment_scores_view.month_number"?: NumericDimensionValue | null;
  /** Month Name -- Full month name (January, February, etc.). */
  "student_assessment_scores_view.month_name"?: string | null;
  /** Discipline -- Course discipline from the course-subject crosswalk — broad grouping (ELA, Math, Science, Social Studies, CCR, World Language). Distinct from the assessment's academic_subject, which is the granular subject tested. (dim_courses.academic_subject is sourced from csc.discipline.) */
  "student_assessment_scores_view.discipline"?: string | null;
  /** Course Title -- Course name. */
  "student_assessment_scores_view.course_title"?: string | null;
  /** Course Code -- PowerSchool course number. */
  "student_assessment_scores_view.course_code"?: string | null;
  /** Credit Type -- Credit type for the course. */
  "student_assessment_scores_view.credit_type"?: string | null;
  /** Is Foundations -- TRUE if this is a Foundations (intervention) course, per the course-subject crosswalk. */
  "student_assessment_scores_view.is_foundations"?: boolean | null;
  /** Identifier -- Section number for this class. */
  "student_assessment_scores_view.identifier"?: string | null;
  /** Period -- Period expression encoding the days/periods the section meets (e.g., '1(A-F)'). */
  "student_assessment_scores_view.period"?: string | null;
  /** Student Section Enrollment Key -- Surrogate key (cc_dcid, _dbt_source_project). Primary key — one row per CC record. */
  "student_assessment_scores_view.student_section_enrollment_key"?:
    string | null;
  /** Student Enrollment Key -- FK to student_school_enrollments (resolved school enrollment stint). */
  "student_assessment_scores_view.student_enrollment_key"?: string | null;
  /** Entry Date -- Date the student enrolled in this section. Cast to TIMESTAMP for Cube time joins. */
  "student_assessment_scores_view.entry_date"?: TimeDimensionValue | null;
  /** Exit Date -- Date the student left this section. Cast to TIMESTAMP for Cube time joins. */
  "student_assessment_scores_view.exit_date"?: TimeDimensionValue | null;
  /** Is Dropped Section -- TRUE if this section enrollment was dropped mid-term (negative section id + early exit). */
  "student_assessment_scores_view.is_dropped_section"?: boolean | null;
  /** Is Dropped Course -- TRUE if all enrollments for this student x course x year were dropped. */
  "student_assessment_scores_view.is_dropped_course"?: boolean | null;
  /** Lead Teacher Staff Key -- FK to staff — the section's Lead Teacher. */
  "student_assessment_scores_view.lead_teacher_staff_key"?: string | null;
  /** Staff Lead Teacher Full Name -- Staff member's preferred name in Last, First Middle format. */
  "student_assessment_scores_view.staff_lead_teacher_full_name"?: string | null;
  /** Staff Lead Teacher First Name -- Staff member's preferred first name. */
  "student_assessment_scores_view.staff_lead_teacher_first_name"?:
    string | null;
  /** Staff Lead Teacher Last Name -- Staff member's preferred last name. */
  "student_assessment_scores_view.staff_lead_teacher_last_name"?: string | null;
  /** Grade Level -- The grade the student is in. Since this is an integer: 0=Kindergarten, -2=Preschool. */
  "student_assessment_scores_view.grade_level"?: NumericDimensionValue | null;
  /** Graduation Year -- Student graduation year. */
  "student_assessment_scores_view.graduation_year"?: NumericDimensionValue | null;
  /** Year in Network -- Count of years the student has been enrolled in the network. Populated on the student's primary enrollment stint per academic year; null on additional same-year stints. */
  "student_assessment_scores_view.year_in_network"?: NumericDimensionValue | null;
  /** Is Retained Year -- TRUE if the student repeated this grade level in the same school compared to the prior academic year. */
  "student_assessment_scores_view.is_retained_year"?: boolean | null;
  /** Is Ell -- TRUE if the student was classified as an English Language Learner during this enrollment stint. FALSE when no ELL span exists for the stint. Newark, Camden, and Paterson draw from historical LEP entry/exit dates; Miami uses a single current-state span. */
  "student_assessment_scores_view.is_ell"?: boolean | null;
  /** Is Iep -- TRUE if the student had an active Individualized Education Program during this enrollment stint. Derived from the latest IEP span by effective date. */
  "student_assessment_scores_view.is_iep"?: boolean | null;
  /** Iep Classification -- IEP placement classification for this enrollment stint (latest span). Examples: Resource Center, In-Class Resource, Self-Contained. NULL when no IEP span exists. */
  "student_assessment_scores_view.iep_classification"?: string | null;
  /** Special Education Code -- NJ state special education code (Newark and Camden only; NULL for Miami and Paterson). */
  "student_assessment_scores_view.special_education_code"?: string | null;
  /** Special Education Name -- Human-readable label for the NJ special education code (Newark and Camden only; NULL for Miami and Paterson). */
  "student_assessment_scores_view.special_education_name"?: string | null;
  /** Special Education Placement -- NJ special education placement category (Newark and Camden only; NULL for Miami and Paterson). */
  "student_assessment_scores_view.special_education_placement"?: string | null;
  /** Is Meal Eligible -- TRUE if the student was eligible for free, reduced-price, or direct certification meals during this enrollment stint. */
  "student_assessment_scores_view.is_meal_eligible"?: boolean | null;
  /** Meal Eligibility -- Meal eligibility category for this enrollment stint. Values: F (Free), R (Reduced), FDC (Free Direct Certification), P (Paid), Unknown. NULL when no meal span exists. */
  "student_assessment_scores_view.meal_eligibility"?: string | null;
  /** Student Key -- Surrogate key derived from student_number. Primary key for the student dimension. */
  "student_assessment_scores_view.student_key"?: string | null;
  /** Full Name -- Student's full name in "Last, First, Mi." format. Matches dim_staff.full_name naming. */
  "student_assessment_scores_view.full_name"?: string | null;
  /** Birth Date */
  "student_assessment_scores_view.birth_date"?: TimeDimensionValue | null;
  /** Lea Student Identifier -- KIPP's own SIS identifier for the student. KIPP is a charter Local Education Agency (LEA) operating within a host public school district; this column is the identifier issued by KIPP as the LEA. Sourced from the SIS student number for NJ regions (and Focus local ID for Miami once Focus lands). Maps to Ed-Fi District / CEDS District-assigned number from KIPP-as-LEA's perspective. */
  "student_assessment_scores_view.lea_student_identifier"?: NumericDimensionValue | null;
  /** State Student Identifier -- The state-assigned student number for the student. In most cases, this number should stay the same from school to school. */
  "student_assessment_scores_view.state_student_identifier"?: string | null;
  /** District Student Identifier -- Host public school district's identifier for the student. Populated for Miami (MDCPS student ID) and null for NJ regions where the host district's ID is not surfaced upstream. Generalizes the previously Miami-only mdcps_student_identifier. Ed-Fi District / CEDS District-assigned number from the host district's perspective. */
  "student_assessment_scores_view.district_student_identifier"?: string | null;
  /** Salesforce Contact ID -- KIPPADB (Salesforce) contact identifier for the student. Populated where the student has a KIPPADB record; null otherwise. Used across KIPPADB consumer tools (Overgrad, alumni tracking, etc.). */
  "student_assessment_scores_view.salesforce_contact_id"?: string | null;
  /** Gender Identity -- Self-identified gender for the student (e.g., M=Male F=Female). Matches Ed-Fi's genderIdentity attribute (modern inclusive naming). */
  "student_assessment_scores_view.gender_identity"?: string | null;
  /** Race -- Racial category for the student. Decoded from PowerSchool ethnicity code to a full category label (e.g., Black/African American, Hispanic or Latino, Not Hispanic or Latino, Two or More Races, White). Cross-model consistency with dim_staff.race. */
  "student_assessment_scores_view.race"?: string | null;
  /** Enrollment Status -- Current enrollment status of the student. Values: Currently Enrolled, Pre-registered, Inactive, Transferred Out, Graduated, Imported as Historical. */
  "student_assessment_scores_view.enrollment_status"?: string | null;
  /** Is Gifted -- TRUE if the student has a gifted-and-talented identification on either the PowerSchool NJ extension or Miami user-fields extension. */
  "student_assessment_scores_view.is_gifted"?: boolean | null;
  /** Location Name -- Canonical location name. */
  "student_assessment_scores_view.location_name"?: string | null;
  /** Abbreviation -- Short display name for the location. */
  "student_assessment_scores_view.abbreviation"?: string | null;
  /** Region Key -- Foreign key to regions. Surrogate key derived from `business_unit_code` so this column hashes exactly the keys produced by `regions.region_key`. Network-level locations (e.g., KIPP NJ) map to KIPP_TAF. */
  "student_assessment_scores_view.region_key"?: string | null;
  /** Grade Band -- Grade band served (ES, MS, HS). */
  "student_assessment_scores_view.grade_band"?: string | null;
  /** Campus -- Physical campus name. Multiple schools may share a campus. */
  "student_assessment_scores_view.campus"?: string | null;
  /** City -- City. Nullable for non-physical rows (e.g., campus rollups). */
  "student_assessment_scores_view.city"?: string | null;
  /** Region Name -- Region name (Camden, Miami, Newark, Paterson, TAF). */
  "student_assessment_scores_view.region_name"?: string | null;
  /** State -- US state (NJ or FL). */
  "student_assessment_scores_view.state"?: string | null;
  /** Semester -- Semester this period falls within. S1 for term_name Q1/Q2, S2 for Q3/Q4. NULL for periods that don't map to a quarter. */
  "student_assessment_scores_view.semester"?: string | null;
  /** Term Name -- Display name for the period. */
  "student_assessment_scores_view.term_name"?: string | null;
  /** Term Code -- Short code for the period (e.g., Q1, Q2, PM1, Fall). */
  "student_assessment_scores_view.term_code"?: string | null;
  /** Term Type -- Category of period (e.g., academic, PM, survey, assessment, fiscal). */
  "student_assessment_scores_view.term_type"?: string | null;
}

/** Student Attendance View -- Student attendance — row-level (one row per student × school day with attendance recorded) and aggregate breakdowns in a single view. For ADA, use the avg_daily_attendance measure rather than rebuilding the ratio from the raw dimensions — it scopes both sides to full membership days with a recorded attendance value, and a hand-rolled SUM(attendance_value) / SUM(membership_value) counts days that were never recorded as absences. Never average a per-row ratio either way. attendance_value (0.0–1.0) is the fractional attendance contribution; membership_value (0.0–1.0) is the school's claim on the student that day (split across schools if dual-enrolled); present_weight equals attendance_value but tardies count 0.67. attendance_category is the coarse rollup (Present, Absent, Tardy, In-School Suspension, Out-of-School Suspension); attendance_code is the raw SIS code for specific drill-down. is_in_session and is_membership_day come from school_calendars and are joined on (date_key, student_school_enrollments.location_key). Contains direct student identifiers — see access_policy for PII gating. CA, tier, and truancy base measures default to year-end snapshots when queried without an anchor — no filter required for year-over-year comparisons. For a point-in-time result, add a single date_day equality filter. For month-over-month or week-over-week trends, use the _month_end or _week_end named measures. Truancy criteria are regional: Miami uses 15+ absences in a 90-day rolling window; NJ regions use projected 50+ absences for the year. */
export type StudentAttendanceViewMeasure =
  | "student_attendance_view.count_students"
  | "student_attendance_view.avg_daily_attendance"
  | "student_attendance_view.pct_tardy"
  | "student_attendance_view.pct_ontime"
  | "student_attendance_view.count_truants"
  | "student_attendance_view.pct_truant"
  | "student_attendance_view.count_truants_year_end"
  | "student_attendance_view.pct_truant_year_end"
  | "student_attendance_view.count_truants_month_end"
  | "student_attendance_view.pct_truant_month_end"
  | "student_attendance_view.count_truants_week_end"
  | "student_attendance_view.pct_truant_week_end"
  | "student_attendance_view.count_absent_days"
  | "student_attendance_view.count_chronically_absent"
  | "student_attendance_view.pct_chronically_absent"
  | "student_attendance_view.pct_tier_1_2"
  | "student_attendance_view.pct_tier_3"
  | "student_attendance_view.count_chronically_absent_year_end"
  | "student_attendance_view.pct_chronically_absent_year_end"
  | "student_attendance_view.pct_tier_1_2_year_end"
  | "student_attendance_view.pct_tier_3_year_end"
  | "student_attendance_view.count_chronically_absent_month_end"
  | "student_attendance_view.pct_chronically_absent_month_end"
  | "student_attendance_view.pct_tier_1_2_month_end"
  | "student_attendance_view.pct_tier_3_month_end"
  | "student_attendance_view.count_chronically_absent_week_end"
  | "student_attendance_view.pct_chronically_absent_week_end"
  | "student_attendance_view.pct_tier_1_2_week_end"
  | "student_attendance_view.pct_tier_3_week_end";

export type StudentAttendanceViewDimension =
  | "student_attendance_view.attendance_date"
  | "student_attendance_view.attendance_code"
  | "student_attendance_view.attendance_category"
  | "student_attendance_view.ada_tier"
  | "student_attendance_view.attendance_value"
  | "student_attendance_view.membership_value"
  | "student_attendance_view.present_weight"
  | "student_attendance_view.is_absent"
  | "student_attendance_view.is_tardy"
  | "student_attendance_view.is_ontime"
  | "student_attendance_view.is_oss"
  | "student_attendance_view.is_iss"
  | "student_attendance_view.is_suspended"
  | "student_attendance_view.is_truant"
  | "student_attendance_view.is_chronically_absent"
  | "student_attendance_view.is_latest_record"
  | "student_attendance_view.is_month_end_record"
  | "student_attendance_view.is_week_end_record"
  | "student_attendance_view.dates_academic_year"
  | "student_attendance_view.dates_academic_year_label"
  | "student_attendance_view.dates_date_day"
  | "student_attendance_view.dates_month_number"
  | "student_attendance_view.dates_month_name"
  | "student_attendance_view.dates_quarter_number"
  | "student_attendance_view.dates_school_week_start_date"
  | "student_attendance_view.dates_day_of_week_name"
  | "student_attendance_view.dates_is_weekday"
  | "student_attendance_view.locations_location_name"
  | "student_attendance_view.locations_abbreviation"
  | "student_attendance_view.locations_region_key"
  | "student_attendance_view.locations_grade_band"
  | "student_attendance_view.locations_campus"
  | "student_attendance_view.locations_city"
  | "student_attendance_view.regions_region_name"
  | "student_attendance_view.regions_state"
  | "student_attendance_view.student_enrollment_key"
  | "student_attendance_view.grade_level"
  | "student_attendance_view.graduation_year"
  | "student_attendance_view.entry_date"
  | "student_attendance_view.exit_date"
  | "student_attendance_view.is_retained_year"
  | "student_attendance_view.staff_homeroom_teacher_full_name"
  | "student_attendance_view.staff_homeroom_teacher_first_name"
  | "student_attendance_view.staff_homeroom_teacher_last_name"
  | "student_attendance_view.is_ell"
  | "student_attendance_view.is_iep"
  | "student_attendance_view.iep_classification"
  | "student_attendance_view.special_education_code"
  | "student_attendance_view.special_education_name"
  | "student_attendance_view.special_education_placement"
  | "student_attendance_view.is_meal_eligible"
  | "student_attendance_view.meal_eligibility"
  | "student_attendance_view.student_key"
  | "student_attendance_view.full_name"
  | "student_attendance_view.birth_date"
  | "student_attendance_view.lea_student_identifier"
  | "student_attendance_view.state_student_identifier"
  | "student_attendance_view.gender_identity"
  | "student_attendance_view.race"
  | "student_attendance_view.enrollment_status"
  | "student_attendance_view.is_gifted"
  | "student_attendance_view.terms_semester"
  | "student_attendance_view.terms_term_name"
  | "student_attendance_view.terms_term_code"
  | "student_attendance_view.terms_term_type"
  | "student_attendance_view.school_calendars_is_in_session"
  | "student_attendance_view.school_calendars_is_membership_day";

export type StudentAttendanceViewTimeDimension =
  | "student_attendance_view.attendance_date"
  | "student_attendance_view.dates_date_day"
  | "student_attendance_view.dates_school_week_start_date"
  | "student_attendance_view.entry_date"
  | "student_attendance_view.exit_date"
  | "student_attendance_view.birth_date";

export type StudentAttendanceViewMember =
  StudentAttendanceViewMeasure | StudentAttendanceViewDimension;

/** A `/load` row from `student_attendance_view`. */
export interface StudentAttendanceViewRow {
  /** Count Students */
  "student_attendance_view.count_students"?: MeasureValue | null;
  /** Avg Daily Attendance -- Average Daily Attendance (ADA) — attendance value summed over full membership days, divided by the count of those days. Days with no recorded attendance value are excluded from both numerator and denominator, matching the attendance dashboard; counting them in the denominator alone would report them as absences. */
  "student_attendance_view.avg_daily_attendance"?: MeasureValue | null;
  /** Pct Tardy -- Percentage of present days where the student was tardy (tardy days / present days). Absent days and days with no recorded attendance value are excluded from both numerator and denominator. Date filter behavior: filtering to a single date returns that day's tardy rate only. For a cumulative YTD rate as of a given date, use a date range from the start of the academic year (e.g. 2025-07-01 through the target date). */
  "student_attendance_view.pct_tardy"?: MeasureValue | null;
  /** Pct Ontime -- Percentage of present days where the student arrived on time (on-time days / present days). Complement of pct_tardy. Absent days and days with no recorded attendance value are excluded from both numerator and denominator. Date filter behavior: filtering to a single date returns that day's on-time rate only. For a cumulative YTD rate as of a given date, use a date range from the start of the academic year (e.g. 2025-07-01 through the target date). */
  "student_attendance_view.pct_ontime"?: MeasureValue | null;
  /** Count Truants -- Students meeting truancy criteria across the filtered period. For a point-in-time snapshot, filter to a single date. */
  "student_attendance_view.count_truants"?: MeasureValue | null;
  /** Pct Truant -- Percentage of students meeting truancy criteria */
  "student_attendance_view.pct_truant"?: MeasureValue | null;
  /** Count Truants Year End -- Year-end truancy count — students meeting truancy criteria at the final snapshot of each academic year. Safe for year-over-year comparisons without an anchor filter. */
  "student_attendance_view.count_truants_year_end"?: MeasureValue | null;
  /** Pct Truant Year End -- Year-end truancy rate — count_truants_year_end / eligible students at year-end. */
  "student_attendance_view.pct_truant_year_end"?: MeasureValue | null;
  /** Count Truants Month End -- Month-end truancy count — students meeting truancy criteria as of the last school day of each calendar month. Use with timeDimensions granularity "month" for month-over-month truancy trends. */
  "student_attendance_view.count_truants_month_end"?: MeasureValue | null;
  /** Pct Truant Month End -- Month-end truancy rate — count_truants_month_end / eligible students at month-end. Use with timeDimensions granularity "month". */
  "student_attendance_view.pct_truant_month_end"?: MeasureValue | null;
  /** Count Truants Week End -- Week-end truancy count — students meeting truancy criteria as of the last school day of each PowerSchool school week. Group by dates_school_week_start_date for week-over-week truancy trends. */
  "student_attendance_view.count_truants_week_end"?: MeasureValue | null;
  /** Pct Truant Week End -- Week-end truancy rate — count_truants_week_end / eligible students at week-end. group by dates_school_week_start_date. */
  "student_attendance_view.pct_truant_week_end"?: MeasureValue | null;
  /** Count Absent Days -- Total number of absence days (sum of is_absent). Filtered to membership_value > 0 to exclude non-enrollment days while retaining partial-membership days (dual-enrolled students). Not restricted to membership_value = 1 — partial days count as absences too. */
  "student_attendance_view.count_absent_days"?: MeasureValue | null;
  /** Count Chronically Absent -- Students with cumulative ADA < 90% as of the snapshot date. Always use exactly one of the two CA query patterns — never omit both. Year-end / year-over-year: filter is_latest_record = true and group by academic_year. Returns the final CA count per year — last day of school for completed years, today for the current year. Use for comparisons like "CA rate in 2023 vs 2024 vs 2025." Point-in-time: filter to a single date_key (e.g. 2025-11-01). Returns CA status accumulated from the start of the year through that date. Use for same-point-in-year comparisons like "CA as of November 1 each year." Omitting both overcounts — a student CA on 30 days is counted 30 times. Combining both is valid only when the date equals today. */
  "student_attendance_view.count_chronically_absent"?: MeasureValue | null;
  /** Pct Chronically Absent -- Chronic absence rate — count_chronically_absent / _count_ca_eligible_students. Same two query patterns as count_chronically_absent: filter is_latest_record = true for year-end / year-over-year, or a single date_key for point-in-time. Must use exactly one. */
  "student_attendance_view.pct_chronically_absent"?: MeasureValue | null;
  /** Pct Tier12 -- Percentage of CA-eligible students with cumulative ADA ≥ 90% (Tier 1 or Tier 2) as of the snapshot date. Denominator is _count_ca_eligible_students (same as pct_chronically_absent). Use exactly one query pattern: filter is_latest_record = true for year-end / year-over-year, or filter to a single date_key for point-in-time. Omitting both overcounts. */
  "student_attendance_view.pct_tier_1_2"?: MeasureValue | null;
  /** Pct Tier3 -- Percentage of CA-eligible students with cumulative ADA 80–89% (Tier 3) as of the snapshot date. Denominator is _count_ca_eligible_students. Use exactly one query pattern: filter is_latest_record = true for year-end / year-over-year, or filter to a single date_key for point-in-time. Omitting both overcounts. */
  "student_attendance_view.pct_tier_3"?: MeasureValue | null;
  /** Count Chronically Absent Year End -- Year-end chronic absence count — students with cumulative ADA < 90% at the final snapshot of each academic year (last school day for completed years, today for the current year). Safe for year-over-year comparisons without an anchor filter. */
  "student_attendance_view.count_chronically_absent_year_end"?: MeasureValue | null;
  /** Pct Chronically Absent Year End -- Year-end chronic absence rate — count_chronically_absent_year_end / eligible students at year-end. Safe for year-over-year comparisons without an anchor filter. */
  "student_attendance_view.pct_chronically_absent_year_end"?: MeasureValue | null;
  /** Pct Tier12 Year End -- Year-end percentage of CA-eligible students with cumulative ADA ≥ 90% (Tier 1 or Tier 2). Safe for year-over-year comparisons without an anchor filter. */
  "student_attendance_view.pct_tier_1_2_year_end"?: MeasureValue | null;
  /** Pct Tier3 Year End -- Year-end percentage of CA-eligible students with cumulative ADA 80–89% (Tier 3). Safe for year-over-year comparisons without an anchor filter. */
  "student_attendance_view.pct_tier_3_year_end"?: MeasureValue | null;
  /** Count Chronically Absent Month End -- Month-end chronic absence count — students with cumulative ADA < 90% as of the last school day of each calendar month. Use with timeDimensions granularity "month" for month-over-month CA trends. */
  "student_attendance_view.count_chronically_absent_month_end"?: MeasureValue | null;
  /** Pct Chronically Absent Month End -- Month-end chronic absence rate — count_chronically_absent_month_end / eligible students at month-end. Use with timeDimensions granularity "month" for month-over-month CA trends. */
  "student_attendance_view.pct_chronically_absent_month_end"?: MeasureValue | null;
  /** Pct Tier12 Month End -- Month-end percentage of CA-eligible students with cumulative ADA ≥ 90% (Tier 1 or Tier 2). Use with timeDimensions granularity "month". */
  "student_attendance_view.pct_tier_1_2_month_end"?: MeasureValue | null;
  /** Pct Tier3 Month End -- Month-end percentage of CA-eligible students with cumulative ADA 80–89% (Tier 3). Use with timeDimensions granularity "month". */
  "student_attendance_view.pct_tier_3_month_end"?: MeasureValue | null;
  /** Count Chronically Absent Week End -- Week-end chronic absence count — students with cumulative ADA < 90% as of the last school day of each PowerSchool school week. Group by dates_school_week_start_date for week-over-week CA trends. Handles shortened weeks (e.g. last school day is Wednesday). */
  "student_attendance_view.count_chronically_absent_week_end"?: MeasureValue | null;
  /** Pct Chronically Absent Week End -- Week-end chronic absence rate — count_chronically_absent_week_end / eligible students at week-end. group by dates_school_week_start_date for week-over-week CA trends. */
  "student_attendance_view.pct_chronically_absent_week_end"?: MeasureValue | null;
  /** Pct Tier12 Week End -- Week-end percentage of CA-eligible students with cumulative ADA ≥ 90% (Tier 1 or Tier 2). group by dates_school_week_start_date. */
  "student_attendance_view.pct_tier_1_2_week_end"?: MeasureValue | null;
  /** Pct Tier3 Week End -- Week-end percentage of CA-eligible students with cumulative ADA 80–89% (Tier 3). group by dates_school_week_start_date. */
  "student_attendance_view.pct_tier_3_week_end"?: MeasureValue | null;
  /** Attendance Date */
  "student_attendance_view.attendance_date"?: TimeDimensionValue | null;
  /** Attendance Code -- Attendance identifier set by school. Examples Tardy, Absent, etc. */
  "student_attendance_view.attendance_code"?: string | null;
  /** Attendance Category -- Coarse attendance category derived from the is_* flags with priority ordering (suspension > absent > tardy > present). Values: Out-of-School Suspension, In-School Suspension, Absent, Tardy, Present. Use this column for GROUP BY in BI tools; use the raw attendance_code for specific-code drill-down. */
  "student_attendance_view.attendance_category"?: string | null;
  /** Ada Tier -- ADA tier based on cumulative attendance rate through this date. Tier 1 = 95%+ (on track). Tier 2 = 90–94% (at risk). Tier 3 = 80–89% (chronic). Tier 4 = below 80% (severe chronic). */
  "student_attendance_view.ada_tier"?: string | null;
  /** Attendance Value -- Daily attendance value — a real number, typically a fraction of 1 where 1 is a full attendance day. Used with membership_value to compute ADA. Precision depends on the source SIS's attendance mode (full-day vs period-level vs day-part); see source_model for provenance. */
  "student_attendance_view.attendance_value"?: NumericDimensionValue | null;
  /** Membership Value -- The amount of a student's membership this school claims. If a student attends more than one school each one will only be able to claim a certain portion of the membership. The largest number for this will usually be 1 and fractions expressed as decimals. Like .5 or .25. */
  "student_attendance_view.membership_value"?: NumericDimensionValue | null;
  /** Present Weight -- Weighted presence value. 0.67 for tardy (T-prefix codes), otherwise equals attendance_value. Fractional by design — not a 0/1 flag. */
  "student_attendance_view.present_weight"?: NumericDimensionValue | null;
  /** Is Absent -- 1 if the student was absent, 0 if present. Sum-friendly flag. */
  "student_attendance_view.is_absent"?: NumericDimensionValue | null;
  /** Is Tardy -- 1 if the student was tardy (T-prefix attendance code), 0 otherwise. */
  "student_attendance_view.is_tardy"?: NumericDimensionValue | null;
  /** Is Ontime -- 1 if the attendance code is not a T-prefix tardy code, 0 if tardy. Note: this is 1 for absent days as well as on-time present days — use pct_ontime for an on-time rate that correctly excludes absent days. */
  "student_attendance_view.is_ontime"?: NumericDimensionValue | null;
  /** Is Oss -- 1 if the student received out-of-school suspension on this date (OS, OSS, OSSP, SHI codes), 0 otherwise. */
  "student_attendance_view.is_oss"?: NumericDimensionValue | null;
  /** Is Iss -- 1 if the student received in-school suspension on this date (S, ISS codes), 0 otherwise. */
  "student_attendance_view.is_iss"?: NumericDimensionValue | null;
  /** Is Suspended -- 1 if the student was suspended (any type) on this date. Union of is_oss and is_iss codes. */
  "student_attendance_view.is_suspended"?: NumericDimensionValue | null;
  /** Is Truant -- TRUE if the student meets regional truancy criteria. Miami: 15+ absences in 90-day rolling window. NJ regions: projected absences reach 50+ for the year. */
  "student_attendance_view.is_truant"?: boolean | null;
  /** Is Chronically Absent -- TRUE if the student's cumulative ADA through this date is below 90%. Computed on full membership days only (membership_value = 1). Filter to a single date to get YTD CA status as of that date. */
  "student_attendance_view.is_chronically_absent"?: boolean | null;
  /** Is Latest Record -- TRUE on the most recent attendance row per student enrollment (partitioned by student × district × academic year × entry date). For completed academic years this is the last instructional day on record; for the current year it is the most recent day with data. Use as a filter (is_latest_record = true) with dates.academic_year or dates.academic_year_label to get year-end CA status for year-over-year comparisons — one terminal snapshot per enrollment, no date filter required. Do not combine with a date_key filter — use exactly one or the other. Transfer student note: a student who transfers intra-district mid-year has two enrollment records for the same academic_year, so two rows get is_latest_record = true. Cube CA measures use count_distinct on student_enrollment_key. Raw SQL filtering on is_latest_record = true without COUNT DISTINCT will double-count transfer students. */
  "student_attendance_view.is_latest_record"?: boolean | null;
  /** Is Month End Record -- TRUE on the last full membership day of each calendar month per student enrollment. Use with timeDimensions granularity "month" for month-over-month CA trends. Prefer count_chronically_absent_month_end over the base measure when trending by month. */
  "student_attendance_view.is_month_end_record"?: boolean | null;
  /** Is Week End Record -- TRUE on the last full membership day (membership_value = 1) of each PowerSchool school week per student enrollment. Group the CA weekly trend (count_chronically_absent_week_end, pct_tier_*_week_end, count_truants_week_end) by dates_school_week_start_date — not Cube's ISO week granularity. Correctly handles shortened weeks. */
  "student_attendance_view.is_week_end_record"?: boolean | null;
  /** Dates Academic Year -- KIPP academic year (July start). The calendar year in which the academic year begins (e.g., 2025 for the 2025-26 school year). For filtering by year, prefer academic_year_label (the unambiguous "2025-2026" string form) over this integer. */
  "student_attendance_view.dates_academic_year"?: NumericDimensionValue | null;
  /** Dates Academic Year Label -- Full span label for the academic year (e.g. "2025-2026" for the year beginning July 2025). Use this as the canonical filter surface when querying by year — it is unambiguous regardless of SY vs. start-year notation. academic_year 2025 = academic_year_label "2025-2026" = SY26. The integer academic_year is retained for sort/group/math only. */
  "student_attendance_view.dates_academic_year_label"?: string | null;
  /** Dates Date Day -- Timestamp cast of date_key. Required by Cube for date dimension joins. */
  "student_attendance_view.dates_date_day"?: TimeDimensionValue | null;
  /** Dates Month Number -- Month number (1-12). */
  "student_attendance_view.dates_month_number"?: NumericDimensionValue | null;
  /** Dates Month Name -- Full month name (January, February, etc.). */
  "student_attendance_view.dates_month_name"?: string | null;
  /** Dates Quarter Number -- Calendar quarter (1-4). */
  "student_attendance_view.dates_quarter_number"?: NumericDimensionValue | null;
  /** Dates School Week Start Date */
  "student_attendance_view.dates_school_week_start_date"?: TimeDimensionValue | null;
  /** Dates Day of Week Name -- Full day name (Monday, Tuesday, etc.). */
  "student_attendance_view.dates_day_of_week_name"?: string | null;
  /** Dates Is Weekday -- TRUE for Monday through Friday. */
  "student_attendance_view.dates_is_weekday"?: boolean | null;
  /** Locations Location Name -- Canonical location name. */
  "student_attendance_view.locations_location_name"?: string | null;
  /** Locations Abbreviation -- Short display name for the location. */
  "student_attendance_view.locations_abbreviation"?: string | null;
  /** Locations Region Key -- Foreign key to regions. Surrogate key derived from `business_unit_code` so this column hashes exactly the keys produced by `regions.region_key`. Network-level locations (e.g., KIPP NJ) map to KIPP_TAF. */
  "student_attendance_view.locations_region_key"?: string | null;
  /** Locations Grade Band -- Grade band served (ES, MS, HS). */
  "student_attendance_view.locations_grade_band"?: string | null;
  /** Locations Campus -- Physical campus name. Multiple schools may share a campus. */
  "student_attendance_view.locations_campus"?: string | null;
  /** Locations City -- City. Nullable for non-physical rows (e.g., campus rollups). */
  "student_attendance_view.locations_city"?: string | null;
  /** Regions Region Name -- Region name (Camden, Miami, Newark, Paterson, TAF). */
  "student_attendance_view.regions_region_name"?: string | null;
  /** Regions State -- US state (NJ or FL). */
  "student_attendance_view.regions_state"?: string | null;
  /** Student Enrollment Key -- Surrogate key derived from student_number, _dbt_source_project, academic_year, and entrydate. Primary key for this dimension — matches the uniqueness grain on int_powerschool__student_enrollment_union. */
  "student_attendance_view.student_enrollment_key"?: string | null;
  /** Grade Level -- The grade the student is in. Since this is an integer: 0=Kindergarten, -2=Preschool. */
  "student_attendance_view.grade_level"?: NumericDimensionValue | null;
  /** Graduation Year -- Student graduation year. */
  "student_attendance_view.graduation_year"?: NumericDimensionValue | null;
  /** Entry Date */
  "student_attendance_view.entry_date"?: TimeDimensionValue | null;
  /** Exit Date */
  "student_attendance_view.exit_date"?: TimeDimensionValue | null;
  /** Is Retained Year -- TRUE if the student repeated this grade level in the same school compared to the prior academic year. */
  "student_attendance_view.is_retained_year"?: boolean | null;
  /** Staff Homeroom Teacher Full Name -- Staff member's preferred name in Last, First Middle format. */
  "student_attendance_view.staff_homeroom_teacher_full_name"?: string | null;
  /** Staff Homeroom Teacher First Name -- Staff member's preferred first name. */
  "student_attendance_view.staff_homeroom_teacher_first_name"?: string | null;
  /** Staff Homeroom Teacher Last Name -- Staff member's preferred last name. */
  "student_attendance_view.staff_homeroom_teacher_last_name"?: string | null;
  /** Is Ell -- TRUE if the student was classified as an English Language Learner during this enrollment stint. FALSE when no ELL span exists for the stint. Newark, Camden, and Paterson draw from historical LEP entry/exit dates; Miami uses a single current-state span. */
  "student_attendance_view.is_ell"?: boolean | null;
  /** Is Iep -- TRUE if the student had an active Individualized Education Program during this enrollment stint. Derived from the latest IEP span by effective date. */
  "student_attendance_view.is_iep"?: boolean | null;
  /** Iep Classification -- IEP placement classification for this enrollment stint (latest span). Examples: Resource Center, In-Class Resource, Self-Contained. NULL when no IEP span exists. */
  "student_attendance_view.iep_classification"?: string | null;
  /** Special Education Code -- NJ state special education code (Newark and Camden only; NULL for Miami and Paterson). */
  "student_attendance_view.special_education_code"?: string | null;
  /** Special Education Name -- Human-readable label for the NJ special education code (Newark and Camden only; NULL for Miami and Paterson). */
  "student_attendance_view.special_education_name"?: string | null;
  /** Special Education Placement -- NJ special education placement category (Newark and Camden only; NULL for Miami and Paterson). */
  "student_attendance_view.special_education_placement"?: string | null;
  /** Is Meal Eligible -- TRUE if the student was eligible for free, reduced-price, or direct certification meals during this enrollment stint. */
  "student_attendance_view.is_meal_eligible"?: boolean | null;
  /** Meal Eligibility -- Meal eligibility category for this enrollment stint. Values: F (Free), R (Reduced), FDC (Free Direct Certification), P (Paid), Unknown. NULL when no meal span exists. */
  "student_attendance_view.meal_eligibility"?: string | null;
  /** Student Key -- Surrogate key derived from student_number. Primary key for the student dimension. */
  "student_attendance_view.student_key"?: string | null;
  /** Full Name -- Student's full name in "Last, First, Mi." format. Matches dim_staff.full_name naming. */
  "student_attendance_view.full_name"?: string | null;
  /** Birth Date */
  "student_attendance_view.birth_date"?: TimeDimensionValue | null;
  /** Lea Student Identifier -- KIPP's own SIS identifier for the student. KIPP is a charter Local Education Agency (LEA) operating within a host public school district; this column is the identifier issued by KIPP as the LEA. Sourced from the SIS student number for NJ regions (and Focus local ID for Miami once Focus lands). Maps to Ed-Fi District / CEDS District-assigned number from KIPP-as-LEA's perspective. */
  "student_attendance_view.lea_student_identifier"?: NumericDimensionValue | null;
  /** State Student Identifier -- The state-assigned student number for the student. In most cases, this number should stay the same from school to school. */
  "student_attendance_view.state_student_identifier"?: string | null;
  /** Gender Identity -- Self-identified gender for the student (e.g., M=Male F=Female). Matches Ed-Fi's genderIdentity attribute (modern inclusive naming). */
  "student_attendance_view.gender_identity"?: string | null;
  /** Race -- Racial category for the student. Decoded from PowerSchool ethnicity code to a full category label (e.g., Black/African American, Hispanic or Latino, Not Hispanic or Latino, Two or More Races, White). Cross-model consistency with dim_staff.race. */
  "student_attendance_view.race"?: string | null;
  /** Enrollment Status -- Current enrollment status of the student. Values: Currently Enrolled, Pre-registered, Inactive, Transferred Out, Graduated, Imported as Historical. */
  "student_attendance_view.enrollment_status"?: string | null;
  /** Is Gifted -- TRUE if the student has a gifted-and-talented identification on either the PowerSchool NJ extension or Miami user-fields extension. */
  "student_attendance_view.is_gifted"?: boolean | null;
  /** Terms Semester -- Semester this period falls within. S1 for term_name Q1/Q2, S2 for Q3/Q4. NULL for periods that don't map to a quarter. */
  "student_attendance_view.terms_semester"?: string | null;
  /** Terms Term Name -- Display name for the period. */
  "student_attendance_view.terms_term_name"?: string | null;
  /** Terms Term Code -- Short code for the period (e.g., Q1, Q2, PM1, Fall). */
  "student_attendance_view.terms_term_code"?: string | null;
  /** Terms Term Type -- Category of period (e.g., academic, PM, survey, assessment, fiscal). */
  "student_attendance_view.terms_term_type"?: string | null;
  /** School Calendars Is in Session -- TRUE if this date is an instructional day at this school. */
  "student_attendance_view.school_calendars_is_in_session"?: boolean | null;
  /** School Calendars Is Membership Day -- TRUE if this date counts toward student membership at this school. */
  "student_attendance_view.school_calendars_is_membership_day"?: boolean | null;
}

/** Student Enrollments View -- Point-in-time student enrollment — row-level (one row per enrolled student-day, for roster exports and questions like "who was enrolled on October 1?"; pin a single date by filtering dates_date_day) and aggregate headcount breakdowns in a single view. count_students is point-in-time (as of the most recent in-session day in the query, or the pinned date). */
export type StudentEnrollmentsViewMeasure =
  "student_enrollments_view.count_students";

export type StudentEnrollmentsViewDimension =
  | "student_enrollments_view.student_attendance_daily_key"
  | "student_enrollments_view.student_enrollment_key"
  | "student_enrollments_view.is_current_record"
  | "student_enrollments_view.is_month_end_record"
  | "student_enrollments_view.is_week_end_record"
  | "student_enrollments_view.is_latest_record"
  | "student_enrollments_view.dates_date_day"
  | "student_enrollments_view.dates_month_number"
  | "student_enrollments_view.dates_month_name"
  | "student_enrollments_view.dates_quarter_number"
  | "student_enrollments_view.dates_academic_year"
  | "student_enrollments_view.dates_school_week_start_date"
  | "student_enrollments_view.locations_location_name"
  | "student_enrollments_view.locations_abbreviation"
  | "student_enrollments_view.locations_region_key"
  | "student_enrollments_view.locations_grade_band"
  | "student_enrollments_view.locations_campus"
  | "student_enrollments_view.locations_city"
  | "student_enrollments_view.regions_region_name"
  | "student_enrollments_view.regions_state"
  | "student_enrollments_view.student_key"
  | "student_enrollments_view.full_name"
  | "student_enrollments_view.birth_date"
  | "student_enrollments_view.lea_student_identifier"
  | "student_enrollments_view.state_student_identifier"
  | "student_enrollments_view.gender_identity"
  | "student_enrollments_view.race"
  | "student_enrollments_view.is_gifted"
  | "student_enrollments_view.enrollment_status"
  | "student_enrollments_view.grade_level"
  | "student_enrollments_view.graduation_year"
  | "student_enrollments_view.is_retained_year"
  | "student_enrollments_view.staff_homeroom_teacher_full_name"
  | "student_enrollments_view.staff_homeroom_teacher_first_name"
  | "student_enrollments_view.staff_homeroom_teacher_last_name"
  | "student_enrollments_view.is_ell"
  | "student_enrollments_view.is_iep"
  | "student_enrollments_view.iep_classification"
  | "student_enrollments_view.special_education_code"
  | "student_enrollments_view.special_education_name"
  | "student_enrollments_view.special_education_placement"
  | "student_enrollments_view.is_meal_eligible"
  | "student_enrollments_view.meal_eligibility";

export type StudentEnrollmentsViewTimeDimension =
  | "student_enrollments_view.dates_date_day"
  | "student_enrollments_view.dates_school_week_start_date"
  | "student_enrollments_view.birth_date";

export type StudentEnrollmentsViewMember =
  StudentEnrollmentsViewMeasure | StudentEnrollmentsViewDimension;

/** A `/load` row from `student_enrollments_view`. */
export interface StudentEnrollmentsViewRow {
  /** Count Students -- Distinct students enrolled, point-in-time. Counts each student once as of the most recent in-session school day in your query: the exact date if you filter to one (filter dates_date_day to a single date, e.g. 2025-10-01 for the fall count), otherwise each school's latest in-session day in the period (today for the current year, the last day of school for completed years). Group by month or week to trend the point-in-time headcount over the year. Matches the topline Total Enrollment methodology — enrollment is by entry/exit dates, not status. Note: when no single date is pinned, schools that end on different days are each counted as of their own last day, so a network total can mix as-of dates within the final weeks of a year. A week or month with no in-session days (e.g. winter or February break) has no point-in-time snapshot and reads as 0 in a trend — read trends on instructional periods, or carry the prior value forward in the BI layer (the daily fact is in-session-days only by design). */
  "student_enrollments_view.count_students"?: MeasureValue | null;
  /** Student Attendance Daily Key -- Surrogate key derived from student_number, _dbt_source_project, and calendardate. Primary key of the underlying attendance daily fact. */
  "student_enrollments_view.student_attendance_daily_key"?: string | null;
  /** Student Enrollment Key -- FK to student_school_enrollments (the stint dimension). Surrogate key from student_number, _dbt_source_project, academic_year, entrydate. */
  "student_enrollments_view.student_enrollment_key"?: string | null;
  /** Is Current Record -- TRUE on the school's latest attendance day that has occurred (per school × academic year, capped at today). Default point-in-time enrollment anchor — drives count_students at year / no grouping. */
  "student_enrollments_view.is_current_record"?: boolean | null;
  /** Is Month End Record -- TRUE on the school's latest attendance day of each calendar month. Use for month-granularity point-in-time enrollment trends. */
  "student_enrollments_view.is_month_end_record"?: boolean | null;
  /** Is Week End Record -- TRUE on the school's latest attendance day of each PowerSchool school week. Group the weekly trend by dates_school_week_start_date (not Cube's native ISO week). */
  "student_enrollments_view.is_week_end_record"?: boolean | null;
  /** Is Latest Record -- TRUE on the last attendance day of each enrollment stint. Per-stint "served" marker — not a period-end anchor; distinct from is_current_record. */
  "student_enrollments_view.is_latest_record"?: boolean | null;
  /** Dates Date Day -- Timestamp cast of date_key. Required by Cube for date dimension joins. */
  "student_enrollments_view.dates_date_day"?: TimeDimensionValue | null;
  /** Dates Month Number -- Month number (1-12). */
  "student_enrollments_view.dates_month_number"?: NumericDimensionValue | null;
  /** Dates Month Name -- Full month name (January, February, etc.). */
  "student_enrollments_view.dates_month_name"?: string | null;
  /** Dates Quarter Number -- Calendar quarter (1-4). */
  "student_enrollments_view.dates_quarter_number"?: NumericDimensionValue | null;
  /** Dates Academic Year -- KIPP academic year (July start). The calendar year in which the academic year begins (e.g., 2025 for the 2025-26 school year). For filtering by year, prefer academic_year_label (the unambiguous "2025-2026" string form) over this integer. */
  "student_enrollments_view.dates_academic_year"?: NumericDimensionValue | null;
  /** Dates School Week Start Date */
  "student_enrollments_view.dates_school_week_start_date"?: TimeDimensionValue | null;
  /** Locations Location Name -- Canonical location name. */
  "student_enrollments_view.locations_location_name"?: string | null;
  /** Locations Abbreviation -- Short display name for the location. */
  "student_enrollments_view.locations_abbreviation"?: string | null;
  /** Locations Region Key -- Foreign key to regions. Surrogate key derived from `business_unit_code` so this column hashes exactly the keys produced by `regions.region_key`. Network-level locations (e.g., KIPP NJ) map to KIPP_TAF. */
  "student_enrollments_view.locations_region_key"?: string | null;
  /** Locations Grade Band -- Grade band served (ES, MS, HS). */
  "student_enrollments_view.locations_grade_band"?: string | null;
  /** Locations Campus -- Physical campus name. Multiple schools may share a campus. */
  "student_enrollments_view.locations_campus"?: string | null;
  /** Locations City -- City. Nullable for non-physical rows (e.g., campus rollups). */
  "student_enrollments_view.locations_city"?: string | null;
  /** Regions Region Name -- Region name (Camden, Miami, Newark, Paterson, TAF). */
  "student_enrollments_view.regions_region_name"?: string | null;
  /** Regions State -- US state (NJ or FL). */
  "student_enrollments_view.regions_state"?: string | null;
  /** Student Key -- Surrogate key derived from student_number. Primary key for the student dimension. */
  "student_enrollments_view.student_key"?: string | null;
  /** Full Name -- Student's full name in "Last, First, Mi." format. Matches dim_staff.full_name naming. */
  "student_enrollments_view.full_name"?: string | null;
  /** Birth Date */
  "student_enrollments_view.birth_date"?: TimeDimensionValue | null;
  /** Lea Student Identifier -- KIPP's own SIS identifier for the student. KIPP is a charter Local Education Agency (LEA) operating within a host public school district; this column is the identifier issued by KIPP as the LEA. Sourced from the SIS student number for NJ regions (and Focus local ID for Miami once Focus lands). Maps to Ed-Fi District / CEDS District-assigned number from KIPP-as-LEA's perspective. */
  "student_enrollments_view.lea_student_identifier"?: NumericDimensionValue | null;
  /** State Student Identifier -- The state-assigned student number for the student. In most cases, this number should stay the same from school to school. */
  "student_enrollments_view.state_student_identifier"?: string | null;
  /** Gender Identity -- Self-identified gender for the student (e.g., M=Male F=Female). Matches Ed-Fi's genderIdentity attribute (modern inclusive naming). */
  "student_enrollments_view.gender_identity"?: string | null;
  /** Race -- Racial category for the student. Decoded from PowerSchool ethnicity code to a full category label (e.g., Black/African American, Hispanic or Latino, Not Hispanic or Latino, Two or More Races, White). Cross-model consistency with dim_staff.race. */
  "student_enrollments_view.race"?: string | null;
  /** Is Gifted -- TRUE if the student has a gifted-and-talented identification on either the PowerSchool NJ extension or Miami user-fields extension. */
  "student_enrollments_view.is_gifted"?: boolean | null;
  /** Enrollment Status -- Current enrollment status of the student. Values: Currently Enrolled, Pre-registered, Inactive, Transferred Out, Graduated, Imported as Historical. */
  "student_enrollments_view.enrollment_status"?: string | null;
  /** Grade Level -- The grade the student is in. Since this is an integer: 0=Kindergarten, -2=Preschool. */
  "student_enrollments_view.grade_level"?: NumericDimensionValue | null;
  /** Graduation Year -- Student graduation year. */
  "student_enrollments_view.graduation_year"?: NumericDimensionValue | null;
  /** Is Retained Year -- TRUE if the student repeated this grade level in the same school compared to the prior academic year. */
  "student_enrollments_view.is_retained_year"?: boolean | null;
  /** Staff Homeroom Teacher Full Name -- Staff member's preferred name in Last, First Middle format. */
  "student_enrollments_view.staff_homeroom_teacher_full_name"?: string | null;
  /** Staff Homeroom Teacher First Name -- Staff member's preferred first name. */
  "student_enrollments_view.staff_homeroom_teacher_first_name"?: string | null;
  /** Staff Homeroom Teacher Last Name -- Staff member's preferred last name. */
  "student_enrollments_view.staff_homeroom_teacher_last_name"?: string | null;
  /** Is Ell -- TRUE if the student was classified as an English Language Learner during this enrollment stint. FALSE when no ELL span exists for the stint. Newark, Camden, and Paterson draw from historical LEP entry/exit dates; Miami uses a single current-state span. */
  "student_enrollments_view.is_ell"?: boolean | null;
  /** Is Iep -- TRUE if the student had an active Individualized Education Program during this enrollment stint. Derived from the latest IEP span by effective date. */
  "student_enrollments_view.is_iep"?: boolean | null;
  /** Iep Classification -- IEP placement classification for this enrollment stint (latest span). Examples: Resource Center, In-Class Resource, Self-Contained. NULL when no IEP span exists. */
  "student_enrollments_view.iep_classification"?: string | null;
  /** Special Education Code -- NJ state special education code (Newark and Camden only; NULL for Miami and Paterson). */
  "student_enrollments_view.special_education_code"?: string | null;
  /** Special Education Name -- Human-readable label for the NJ special education code (Newark and Camden only; NULL for Miami and Paterson). */
  "student_enrollments_view.special_education_name"?: string | null;
  /** Special Education Placement -- NJ special education placement category (Newark and Camden only; NULL for Miami and Paterson). */
  "student_enrollments_view.special_education_placement"?: string | null;
  /** Is Meal Eligible -- TRUE if the student was eligible for free, reduced-price, or direct certification meals during this enrollment stint. */
  "student_enrollments_view.is_meal_eligible"?: boolean | null;
  /** Meal Eligibility -- Meal eligibility category for this enrollment stint. Values: F (Free), R (Reduced), FDC (Free Direct Certification), P (Paid), Unknown. NULL when no meal span exists. */
  "student_enrollments_view.meal_eligibility"?: string | null;
}

/** Student Section Enrollments View -- Student section enrollments — row-level (one row per student x section enrollment) and aggregate headcounts in a single view. Use for per-teacher class rosters (filter to a lead teacher) and section drill-down. count_students is a distinct-student headcount, correct per teacher — grouped by lead teacher it answers "how many students does this teacher teach?". Contains direct student identifiers — see access_policy for PII gating. */
export type StudentSectionEnrollmentsViewMeasure =
  "student_section_enrollments_view.count_students";

export type StudentSectionEnrollmentsViewDimension =
  | "student_section_enrollments_view.student_section_enrollment_key"
  | "student_section_enrollments_view.student_enrollment_key"
  | "student_section_enrollments_view.academic_year"
  | "student_section_enrollments_view.entry_date"
  | "student_section_enrollments_view.exit_date"
  | "student_section_enrollments_view.is_dropped_section"
  | "student_section_enrollments_view.is_dropped_course"
  | "student_section_enrollments_view.is_homeroom"
  | "student_section_enrollments_view.is_current_section_enrollment"
  | "student_section_enrollments_view.lead_teacher_staff_key"
  | "student_section_enrollments_view.staff_lead_teacher_full_name"
  | "student_section_enrollments_view.staff_lead_teacher_first_name"
  | "student_section_enrollments_view.staff_lead_teacher_last_name"
  | "student_section_enrollments_view.discipline"
  | "student_section_enrollments_view.course_title"
  | "student_section_enrollments_view.course_code"
  | "student_section_enrollments_view.credit_type"
  | "student_section_enrollments_view.is_foundations"
  | "student_section_enrollments_view.identifier"
  | "student_section_enrollments_view.period"
  | "student_section_enrollments_view.semester"
  | "student_section_enrollments_view.term_name"
  | "student_section_enrollments_view.term_code"
  | "student_section_enrollments_view.term_type"
  | "student_section_enrollments_view.grade_level"
  | "student_section_enrollments_view.graduation_year"
  | "student_section_enrollments_view.year_in_network"
  | "student_section_enrollments_view.is_retained_year"
  | "student_section_enrollments_view.student_key"
  | "student_section_enrollments_view.full_name"
  | "student_section_enrollments_view.birth_date"
  | "student_section_enrollments_view.lea_student_identifier"
  | "student_section_enrollments_view.state_student_identifier"
  | "student_section_enrollments_view.gender_identity"
  | "student_section_enrollments_view.race"
  | "student_section_enrollments_view.enrollment_status"
  | "student_section_enrollments_view.is_gifted"
  | "student_section_enrollments_view.locations_location_name"
  | "student_section_enrollments_view.locations_abbreviation"
  | "student_section_enrollments_view.locations_region_key"
  | "student_section_enrollments_view.locations_grade_band"
  | "student_section_enrollments_view.locations_campus"
  | "student_section_enrollments_view.locations_city"
  | "student_section_enrollments_view.regions_region_name"
  | "student_section_enrollments_view.regions_state";

export type StudentSectionEnrollmentsViewTimeDimension =
  | "student_section_enrollments_view.entry_date"
  | "student_section_enrollments_view.exit_date"
  | "student_section_enrollments_view.birth_date";

export type StudentSectionEnrollmentsViewMember =
  StudentSectionEnrollmentsViewMeasure | StudentSectionEnrollmentsViewDimension;

/** A `/load` row from `student_section_enrollments_view`. */
export interface StudentSectionEnrollmentsViewRow {
  /** Count Students -- Distinct students with a section enrollment in the filtered slice. Answers "how many students does this teacher teach?" when grouped by the lead teacher. count_distinct on the student, so it is fan-safe. */
  "student_section_enrollments_view.count_students"?: MeasureValue | null;
  /** Student Section Enrollment Key -- Surrogate key (cc_dcid, _dbt_source_project). Primary key — one row per CC record. */
  "student_section_enrollments_view.student_section_enrollment_key"?:
    string | null;
  /** Student Enrollment Key -- FK to student_school_enrollments (resolved school enrollment stint). */
  "student_section_enrollments_view.student_enrollment_key"?: string | null;
  /** Academic Year -- KIPP academic year (July start) the section enrollment falls in. The calendar year the academic year begins (e.g., 2025 for 2025-26). This is the canonical academic_year for the assessment-scores views. */
  "student_section_enrollments_view.academic_year"?: NumericDimensionValue | null;
  /** Entry Date -- Date the student enrolled in this section. Cast to TIMESTAMP for Cube time joins. */
  "student_section_enrollments_view.entry_date"?: TimeDimensionValue | null;
  /** Exit Date -- Date the student left this section. Cast to TIMESTAMP for Cube time joins. */
  "student_section_enrollments_view.exit_date"?: TimeDimensionValue | null;
  /** Is Dropped Section -- TRUE if this section enrollment was dropped mid-term (negative section id + early exit). */
  "student_section_enrollments_view.is_dropped_section"?: boolean | null;
  /** Is Dropped Course -- TRUE if all enrollments for this student x course x year were dropped. */
  "student_section_enrollments_view.is_dropped_course"?: boolean | null;
  /** Is Homeroom -- TRUE when this is a homeroom section (HR course-number prefix). */
  "student_section_enrollments_view.is_homeroom"?: boolean | null;
  /** Is Current Section Enrollment -- TRUE for the most-recent section enrollment among a student's sequential enrollments in the same course within an academic year. Filter with is_homeroom to select the current homeroom section. */
  "student_section_enrollments_view.is_current_section_enrollment"?:
    boolean | null;
  /** Lead Teacher Staff Key -- FK to staff — the section's Lead Teacher. */
  "student_section_enrollments_view.lead_teacher_staff_key"?: string | null;
  /** Staff Lead Teacher Full Name -- Staff member's preferred name in Last, First Middle format. */
  "student_section_enrollments_view.staff_lead_teacher_full_name"?:
    string | null;
  /** Staff Lead Teacher First Name -- Staff member's preferred first name. */
  "student_section_enrollments_view.staff_lead_teacher_first_name"?:
    string | null;
  /** Staff Lead Teacher Last Name -- Staff member's preferred last name. */
  "student_section_enrollments_view.staff_lead_teacher_last_name"?:
    string | null;
  /** Discipline -- Course discipline from the course-subject crosswalk — broad grouping (ELA, Math, Science, Social Studies, CCR, World Language). Distinct from the assessment's academic_subject, which is the granular subject tested. (dim_courses.academic_subject is sourced from csc.discipline.) */
  "student_section_enrollments_view.discipline"?: string | null;
  /** Course Title -- Course name. */
  "student_section_enrollments_view.course_title"?: string | null;
  /** Course Code -- PowerSchool course number. */
  "student_section_enrollments_view.course_code"?: string | null;
  /** Credit Type -- Credit type for the course. */
  "student_section_enrollments_view.credit_type"?: string | null;
  /** Is Foundations -- TRUE if this is a Foundations (intervention) course, per the course-subject crosswalk. */
  "student_section_enrollments_view.is_foundations"?: boolean | null;
  /** Identifier -- Section number for this class. */
  "student_section_enrollments_view.identifier"?: string | null;
  /** Period -- Period expression encoding the days/periods the section meets (e.g., '1(A-F)'). */
  "student_section_enrollments_view.period"?: string | null;
  /** Semester -- Semester this period falls within. S1 for term_name Q1/Q2, S2 for Q3/Q4. NULL for periods that don't map to a quarter. */
  "student_section_enrollments_view.semester"?: string | null;
  /** Term Name -- Display name for the period. */
  "student_section_enrollments_view.term_name"?: string | null;
  /** Term Code -- Short code for the period (e.g., Q1, Q2, PM1, Fall). */
  "student_section_enrollments_view.term_code"?: string | null;
  /** Term Type -- Category of period (e.g., academic, PM, survey, assessment, fiscal). */
  "student_section_enrollments_view.term_type"?: string | null;
  /** Grade Level -- The grade the student is in. Since this is an integer: 0=Kindergarten, -2=Preschool. */
  "student_section_enrollments_view.grade_level"?: NumericDimensionValue | null;
  /** Graduation Year -- Student graduation year. */
  "student_section_enrollments_view.graduation_year"?: NumericDimensionValue | null;
  /** Year in Network -- Count of years the student has been enrolled in the network. Populated on the student's primary enrollment stint per academic year; null on additional same-year stints. */
  "student_section_enrollments_view.year_in_network"?: NumericDimensionValue | null;
  /** Is Retained Year -- TRUE if the student repeated this grade level in the same school compared to the prior academic year. */
  "student_section_enrollments_view.is_retained_year"?: boolean | null;
  /** Student Key -- Surrogate key derived from student_number. Primary key for the student dimension. */
  "student_section_enrollments_view.student_key"?: string | null;
  /** Full Name -- Student's full name in "Last, First, Mi." format. Matches dim_staff.full_name naming. */
  "student_section_enrollments_view.full_name"?: string | null;
  /** Birth Date */
  "student_section_enrollments_view.birth_date"?: TimeDimensionValue | null;
  /** Lea Student Identifier -- KIPP's own SIS identifier for the student. KIPP is a charter Local Education Agency (LEA) operating within a host public school district; this column is the identifier issued by KIPP as the LEA. Sourced from the SIS student number for NJ regions (and Focus local ID for Miami once Focus lands). Maps to Ed-Fi District / CEDS District-assigned number from KIPP-as-LEA's perspective. */
  "student_section_enrollments_view.lea_student_identifier"?: NumericDimensionValue | null;
  /** State Student Identifier -- The state-assigned student number for the student. In most cases, this number should stay the same from school to school. */
  "student_section_enrollments_view.state_student_identifier"?: string | null;
  /** Gender Identity -- Self-identified gender for the student (e.g., M=Male F=Female). Matches Ed-Fi's genderIdentity attribute (modern inclusive naming). */
  "student_section_enrollments_view.gender_identity"?: string | null;
  /** Race -- Racial category for the student. Decoded from PowerSchool ethnicity code to a full category label (e.g., Black/African American, Hispanic or Latino, Not Hispanic or Latino, Two or More Races, White). Cross-model consistency with dim_staff.race. */
  "student_section_enrollments_view.race"?: string | null;
  /** Enrollment Status -- Current enrollment status of the student. Values: Currently Enrolled, Pre-registered, Inactive, Transferred Out, Graduated, Imported as Historical. */
  "student_section_enrollments_view.enrollment_status"?: string | null;
  /** Is Gifted -- TRUE if the student has a gifted-and-talented identification on either the PowerSchool NJ extension or Miami user-fields extension. */
  "student_section_enrollments_view.is_gifted"?: boolean | null;
  /** Locations Location Name -- Canonical location name. */
  "student_section_enrollments_view.locations_location_name"?: string | null;
  /** Locations Abbreviation -- Short display name for the location. */
  "student_section_enrollments_view.locations_abbreviation"?: string | null;
  /** Locations Region Key -- Foreign key to regions. Surrogate key derived from `business_unit_code` so this column hashes exactly the keys produced by `regions.region_key`. Network-level locations (e.g., KIPP NJ) map to KIPP_TAF. */
  "student_section_enrollments_view.locations_region_key"?: string | null;
  /** Locations Grade Band -- Grade band served (ES, MS, HS). */
  "student_section_enrollments_view.locations_grade_band"?: string | null;
  /** Locations Campus -- Physical campus name. Multiple schools may share a campus. */
  "student_section_enrollments_view.locations_campus"?: string | null;
  /** Locations City -- City. Nullable for non-physical rows (e.g., campus rollups). */
  "student_section_enrollments_view.locations_city"?: string | null;
  /** Regions Region Name -- Region name (Camden, Miami, Newark, Paterson, TAF). */
  "student_section_enrollments_view.regions_region_name"?: string | null;
  /** Regions State -- US state (NJ or FL). */
  "student_section_enrollments_view.regions_state"?: string | null;
}

/** Every view exposed by the semantic layer. */
export type ViewName =
  | "student_attendance_view"
  | "student_enrollments_view"
  | "student_section_enrollments_view"
  | "student_assessment_scores_view"
  | "staff_directory"
  | "staff_pii";

/** Member-name unions per view, keyed by view name. */
export interface ViewMembers {
  student_attendance_view: {
    measure: StudentAttendanceViewMeasure;
    dimension: StudentAttendanceViewDimension;
    timeDimension: StudentAttendanceViewTimeDimension;
    member: StudentAttendanceViewMember;
  };
  student_enrollments_view: {
    measure: StudentEnrollmentsViewMeasure;
    dimension: StudentEnrollmentsViewDimension;
    timeDimension: StudentEnrollmentsViewTimeDimension;
    member: StudentEnrollmentsViewMember;
  };
  student_section_enrollments_view: {
    measure: StudentSectionEnrollmentsViewMeasure;
    dimension: StudentSectionEnrollmentsViewDimension;
    timeDimension: StudentSectionEnrollmentsViewTimeDimension;
    member: StudentSectionEnrollmentsViewMember;
  };
  student_assessment_scores_view: {
    measure: StudentAssessmentScoresViewMeasure;
    dimension: StudentAssessmentScoresViewDimension;
    timeDimension: StudentAssessmentScoresViewTimeDimension;
    member: StudentAssessmentScoresViewMember;
  };
  staff_directory: {
    measure: StaffDirectoryMeasure;
    dimension: StaffDirectoryDimension;
    timeDimension: StaffDirectoryTimeDimension;
    member: StaffDirectoryMember;
  };
  staff_pii: {
    measure: StaffPiiMeasure;
    dimension: StaffPiiDimension;
    timeDimension: StaffPiiTimeDimension;
    member: StaffPiiMember;
  };
}

/** Row shapes per view, keyed by view name. */
export interface ViewRows {
  student_attendance_view: StudentAttendanceViewRow;
  student_enrollments_view: StudentEnrollmentsViewRow;
  student_section_enrollments_view: StudentSectionEnrollmentsViewRow;
  student_assessment_scores_view: StudentAssessmentScoresViewRow;
  staff_directory: StaffDirectoryRow;
  staff_pii: StaffPiiRow;
}

/** A filter clause against one member of view `V`. */
export interface CubeFilter<V extends ViewName> {
  member: ViewMembers[V]["member"];
  operator: FilterOperator;
  /** Omitted for the `set` / `notSet` operators, required otherwise. */
  values?: string[];
}

/** A time-dimension clause against one time member of view `V`. */
export interface CubeTimeDimension<V extends ViewName> {
  dimension: ViewMembers[V]["timeDimension"];
  granularity?: Granularity;
  /** `["2025-08-01", "2026-06-30"]`, or a named range such as `"last week"`. */
  dateRange?: [string, string] | string;
}

/**
 * A `/load` query against view `V`. Member names are checked against the
 * catalog, so a typo or a member from another view fails to compile.
 */
export interface CubeQuery<V extends ViewName> {
  measures?: ViewMembers[V]["measure"][];
  dimensions?: ViewMembers[V]["dimension"][];
  timeDimensions?: CubeTimeDimension<V>[];
  filters?: CubeFilter<V>[];
  order?: Partial<Record<ViewMembers[V]["member"], "asc" | "desc">>;
  limit?: number;
  offset?: number;
  /** IANA name, e.g. `"America/New_York"`. Defaults to UTC when omitted. */
  timezone?: string;
}

/** The envelope returned by `POST /cubejs-api/v1/load`. */
export interface CubeLoadResponse<V extends ViewName> {
  data: ViewRows[V][];
  /** Cube echoes a NORMALISED query here -- not a copy of what you sent. */
  query: CubeQuery<V>;
  annotation: {
    measures: Record<string, unknown>;
    dimensions: Record<string, unknown>;
    timeDimensions: Record<string, unknown>;
  };
}
