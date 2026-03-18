# CLAUDE.md — `models/students/`

Business rules and categorization logic for student-level models. When writing
or reviewing SQL in this directory, implement CASE statements to match these
definitions exactly. When a PR changes a CASE statement that maps to a rule
below, verify the SQL matches — flag any drift.

## GPA Categories

### KTAF GPA Band — Weighted

KIPP TAF internal cut-offs (4 bands). Applied to weighted GPA fields (max 5.33):

- `cumulative_y1_gpa`
- `cumulative_y1_gpa_projected`
- `cumulative_y1_gpa_projected_s1`
- `core_cumulative_y1_gpa`

| Rank | Label        | Min (inclusive) | Max (inclusive) |
| ---- | ------------ | --------------- | --------------- |
| 4    | > 3.00       | 3.00            | 5.33            |
| 3    | 2.50 to 2.99 | 2.50            | 2.99            |
| 2    | 2.00 to 2.49 | 2.00            | 2.49            |
| 1    | < 2.00       | 0.00            | 1.99            |

### KTAF GPA Band — Unweighted

KIPP TAF internal cut-offs (4 bands). Applied to unweighted GPA fields (max
4.33):

- `cumulative_y1_gpa_unweighted`
- `cumulative_y1_gpa_projected_unweighted`
- `cumulative_y1_gpa_projected_s1_unweighted`

| Rank | Label        | Min (inclusive) | Max (inclusive) |
| ---- | ------------ | --------------- | --------------- |
| 4    | > 3.00       | 3.00            | 4.33            |
| 3    | 2.50 to 2.99 | 2.50            | 2.99            |
| 2    | 2.00 to 2.49 | 2.00            | 2.49            |
| 1    | < 2.00       | 0.00            | 1.99            |

### KIPP GPA Band

KIPP Foundation cut-offs (5 bands). Applied to unweighted GPA fields only (same
fields as KTAF GPA Band — Unweighted):

- `cumulative_y1_gpa_unweighted`
- `cumulative_y1_gpa_projected_unweighted`
- `cumulative_y1_gpa_projected_s1_unweighted`

| Rank | Label        | Min (inclusive) | Max (inclusive) |
| ---- | ------------ | --------------- | --------------- |
| 5    | 3.50 to 4.00 | 3.50            | 4.00            |
| 4    | 3.00 to 3.49 | 3.00            | 3.49            |
| 3    | 2.50 to 2.99 | 2.50            | 2.99            |
| 2    | 2.00 to 2.49 | 2.00            | 2.49            |
| 1    | < 2.00       | 0.00            | 1.99            |
