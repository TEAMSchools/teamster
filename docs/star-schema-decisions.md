# Star Schema — Decisions

All decisions resolved. Ready to implement.

Joins between dims and facts are defined in the semantic layer — not in dbt SQL.
Focus here is on grain, surrogate keys, and which attributes belong in each
model.

---

## 1. `dim_students` — add columns

| Column                   | Source field              | Add?                                                |
| ------------------------ | ------------------------- | --------------------------------------------------- |
| `student_name`           | `lastfirst`               | Yes                                                 |
| `region`                 | `region`                  | No — location attribute, belongs in `dim_locations` |
| `school_level`           | `school_level`            | No — location attribute, belongs in `dim_locations` |
| `school`                 | `school_abbreviation`     | No — location attribute, belongs in `dim_locations` |
| `reporting_schoolid`     | `reporting_schoolid`      | No — location attribute, belongs in `dim_locations` |
| `team`                   | `advisory_section_number` | Yes                                                 |
| `is_counseling_services` | spenrollments join        | Yes                                                 |
| `is_student_athlete`     | spenrollments join        | Yes                                                 |

---

## 2. `school_id` in `fct_attendance`

**Resolved.** Not needed — joins handled in the semantic layer.

---

## 3. `nj_overall_student_tier`

**Resolved.** Belongs in the assessments models.

---

## 4. Surrogate keys for staff fact models

| Model                            | Surrogate key columns                                              |
| -------------------------------- | ------------------------------------------------------------------ |
| `fct_staff_attrition`            | `(employee_number, academic_year, attrition_type)`                 |
| `fct_staff_terminations`         | `(employee_number, academic_year)` — see #5                        |
| `fct_staff_benefits_enrollments` | `(employee_number, plan_type, enrollment_start_date)`              |
| `fct_additional_earnings`        | `(employee_number, pay_date, additional_earnings_code, gross_pay)` |
| `fct_microgoals`                 | `assignment_id` (unique on its own)                                |

---

## 5. `fct_staff_terminations` fan-out

**Resolved.** Collapse to one row per `(employee_number, academic_year)` — keep
first/earliest termination by academic year only. Surrogate key is
`(employee_number, academic_year)`.

---

## 6. `dim_seats` — snapshot columns

**Resolved.** Rename `dbt_valid_from` / `dbt_valid_to` to `effective_date_start`
/ `effective_date_end`. Add surrogate key on
`(staffing_model_id, effective_date_start)`.

---

## 7. `dim_locations` join strategy

**Resolved.** `dim_students → dim_locations` join uses enrollment dates (SCD2
date-range) in the semantic layer. No `school_id` FK needed in either
`dim_students` or `fct_attendance`. `dim_staff.location` already matches
`dim_locations.location_clean_name` directly.

---

## 8. State-reported demographics in `fct_state_assessments`

**Resolved.** Keep `state_lep_status`, `state_is_504`, `state_iep_status`,
`state_race_ethnicity` in the fact table. Add YAML descriptions clarifying these
are state-reported values at test time, distinct from KIPP enrollment records in
`dim_students`.
