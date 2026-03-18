# CLAUDE.md — `models/students/`

Business rules and categorization logic for student-level models. When writing
or reviewing SQL in this directory, implement CASE statements to match these
definitions exactly. When a PR changes a CASE statement that maps to a rule
below, verify the SQL matches — flag any drift.

## GPA Categories

Used in `int_extracts__student_enrollments` and downstream academic models.

### Standard GPA Categories

Applied to cumulative and term GPA fields (e.g., `cumulative_gpa`,
`term_gpa`).

| Rank | Category Name | Min (inclusive) | Max (exclusive) |
| ---- | ------------- | --------------- | --------------- |
| 5    | 3.50+         | 3.50            | 4.01            |
| 4    | 3.00–3.49     | 3.00            | 3.50            |
| 3    | 2.50–2.99     | 2.50            | 3.00            |
| 2    | 2.00–2.49     | 2.00            | 2.50            |
| 1    | Below 2.00    | 0.00            | 2.00            |

> **Note**: Add any additional GPA category sets (e.g., weighted GPA, AP GPA)
> as separate subsections here, following the same table format. Include which
> fields and models each set applies to.
