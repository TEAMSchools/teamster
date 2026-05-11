# Identity FK orphans — design

## Goal

Close [#3863](https://github.com/TEAMSchools/teamster/issues/3863)
(`fct_assessment_scores_enrollment_scoped.student_key` orphans) and
[#3647](https://github.com/TEAMSchools/teamster/issues/3647) (cross-system
identity gaps) by favoring direct/natural joins over net-new crosswalk models. A
crosswalk model is built only where no direct join is feasible.

## In scope

- **FLEID** — fix `int_fldoe__all_assessments` to resolve `student_key` via the
  canonical FLEID column on the student record (likely `state_studentnumber` on
  PowerSchool `students`). Resolves
  [#3863](https://github.com/TEAMSchools/teamster/issues/3863) Miami bucket
  (19,916 rows).
- **DeansList** — join DeansList users to `int_people__staff_roster` on email;
  add `staff_key` FK to `fct_behavioral_incidents` with a `relationships` test.
- **Paterson 8** — investigate root cause; fix in place or downgrade the test
  with documented rationale. Closes
  [#3863](https://github.com/TEAMSchools/teamster/issues/3863) Paterson bucket.
- **SmartRecruiters** — audit-only: feasibility of candidate→associate matching
  (email on hire). Build deferred to follow-on issue.

## Out of scope

- `assessment_administration_key` orphans
  ([#3858](https://github.com/TEAMSchools/teamster/issues/3858),
  [#3859](https://github.com/TEAMSchools/teamster/issues/3859)) — different FK,
  different cause.
- Bridge tables for multi-value attributes
  ([#3700](https://github.com/TEAMSchools/teamster/issues/3700)) — separate
  spec.
- Building a SmartRecruiters crosswalk model. Audit only; build (if warranted)
  becomes its own ticket.

## Approach — audit before model

For each identity gap, first confirm whether the source already carries (or can
carry) the canonical key. Build a dedicated crosswalk model only when no direct
join is feasible. Within this spec, that escape hatch is reserved for
SmartRecruiters, where the build is deferred regardless.

## Deliverables

- **PR 1 — direct-key fixes**: FLEID, DeansList, Paterson 8. Includes
  new/updated `relationships` tests as verification gates. Closes
  [#3863](https://github.com/TEAMSchools/teamster/issues/3863) and resolves the
  FLEID + DeansList portions of
  [#3647](https://github.com/TEAMSchools/teamster/issues/3647).
- **PR 2 — SmartRecruiters feasibility audit**: doc-only, no model changes.
  Files a follow-on issue if/when build is warranted. Closes
  [#3647](https://github.com/TEAMSchools/teamster/issues/3647).
- Audit findings (aggregates only) live in PR bodies and commit messages, not in
  this spec.
- PII-bearing investigation detail stays in `.claude/scratch/`.

## Verification gates

- **FLEID**: [#3863](https://github.com/TEAMSchools/teamster/issues/3863)'s
  reproduce query returns 0 Miami rows in dbt Cloud CI.
- **DeansList**: new `relationships` test on
  `fct_behavioral_incidents.staff_key` → staff dimension passes.
- **Paterson 8**: reproduce query returns 0 Paterson rows, or the test is
  downgraded with rationale documented in PR 1.
- **SmartRecruiters**: audit doc merged; follow-on issue exists if build is
  warranted.

## Risks and open assumptions

- **FLEID** assumes `state_studentnumber` is populated for FL-region students on
  PowerSchool. Audit confirms before model change.
- **DeansList** assumes work email is populated on DeansList user records and
  matches `int_people__staff_roster` (`google_email` or equivalent). Audit
  determines fallback handling for unmatched users (NULL FK vs. fuzzy match);
  decision made in PR 1, not pre-committed here.
- **Paterson 8** root cause is unknown. If investigation shows it is not an
  identity gap (e.g., orphan due to enrollment-window logic), the fix may be
  re-routed out of this spec.

## Related

- Parent: [#3647](https://github.com/TEAMSchools/teamster/issues/3647)
- Acceptance test: [#3863](https://github.com/TEAMSchools/teamster/issues/3863)
- Sibling FK orphan trackers (out of scope):
  [#3858](https://github.com/TEAMSchools/teamster/issues/3858),
  [#3859](https://github.com/TEAMSchools/teamster/issues/3859)
- Bridge work (separate spec):
  [#3700](https://github.com/TEAMSchools/teamster/issues/3700)
