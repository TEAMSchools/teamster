# NJ SLEDS Course Roster submission — intern audit runbook and helper-query pack

Design spec for [#4280](https://github.com/TEAMSchools/teamster/issues/4280).

## Context

Each year New Jersey requires two paired SLEDS submissions for the Newark and
Camden districts:

- **Staff Course Roster** — one row per teacher per section taught (19 fields).
- **Student Course Roster** — one row per student per section enrolled (24–26
  fields, including grade/credit/completion).

Together they are a complete schedule-and-transcript record for the year. There
is roughly a one-month window to complete the submission, and the work has
historically required heavy manual auditing for recurring reasons:

1. **New staff lack a state Staff Member Identifier (SMID).** Network growth
   means many new staff each year who need an SMID generated in the state
   system.
2. **Name/DOB drift.** Staff change names or birth dates in the HRIS; those
   changes do not match what the state holds and must be reconciled.
3. **Stale staff IDs.** For long-tenured staff, the ID in the state system does
   not match the HRIS/SIS, because successive ID generations changed local
   systems but not the state record. PowerSchool has state-compliance override
   fields for this, but they are not maintained during the year, so mismatches
   accumulate.
4. **The PowerSchool extract itself is noisy.** It emits records for sections
   with no students, schedule records that do not match a section, and similar
   orphans, which surface as thousands of errors in the state system.

An intern will do the prep work. The intern cannot access the state systems; a
separate staff member with state access performs the upload and reports back the
errors.

## Decisions (load-bearing)

These were settled during brainstorming and drive the whole design:

1. **Intern access:** BigQuery plus Google Sheets, **and** PowerSchool admin.
   The intern fixes sked codes, staff state-ID override fields, and SMID entry
   directly in PowerSchool. The intern does **not** touch state systems.
2. **Cleaning model: source-fix only.** Defects are corrected at the source in
   PowerSchool so the native extract comes out clean. We do **not** rewrite or
   post-filter the extract CSV in BigQuery. The handoff artifact is the
   **regenerated native PowerSchool extract**.
3. **SCED codes live only in PowerSchool fields** (`S_NJ_CRS_X` / `S_NJ_SEC_X`).
   The audit checks presence plus NJ validity on the course/section, not
   crosswalk coverage.
4. **Human-driven, Claude-optional.** The critical path is the BigQuery console
   plus Google Sheets, done by the intern by hand, guided by a self-sufficient
   runbook. This is deliberate: human eyes on the data, the intern builds SQL
   and spreadsheet skills, and **no step may depend on a Claude surface that
   could hit a usage limit and stall progress.** Claude is an optional
   accelerant only.
5. **Intern dataset:** all loaded extracts, reference tables, and durable views
   live in the `cokafor` BigQuery dataset, reading the shared
   `kipptaf_powerschool.*` models read-only. The `awalters` dataset is a source
   of reusable query patterns only.

## Architecture

### The audit loop

Source-fix-only makes this an **iterative loop**, not a one-pass cleanup:

```text
1. PS admin generates Staff + Student Course Roster extracts (Camden, Newark)
2. Intern loads both CSVs into BigQuery (cokafor staging tables)
3. Intern runs the helper-query pack -> defect worklists (Google Sheets)
4. Intern fixes what they own in PowerSchool:
     - sked codes (S_NJ_CRS_X / S_NJ_SEC_X)
     - staff state-ID override fields + SMID entry (S_NJ_USR_X)
     - duplicate / orphan section + schedule cleanup
5. Items the intern cannot own -> compliance-team handoff sheet:
     - generate NEW state SMIDs for new staff
     - push name/DOB changes into Staff Management / state SIS
6. Re-extract -> re-load -> re-run pack -> defects trend toward zero
7. Clean extract handed to the state-access uploader; errors returned -> step 3
```

### Three surfaces, three jobs

The engineering hard wall (BigQuery is reachable only via the VS Code Claude
plugin, never via Claude Desktop) clarifies the surface model:

1. **BigQuery console plus Google Sheets — the critical path.** The intern loads
   extracts into `cokafor`, runs the documented helper queries by hand, and
   builds worklists in Sheets. Self-sufficient: a human can execute the entire
   runbook with zero Claude access. All row-level PII stays here, in-tenant.
2. **VS Code Claude Code plugin — the only governed AI-plus-BigQuery path
   (optional).** Available to help draft or debug a query when the intern wants
   it, but never required; the documented SQL is always the fallback.
3. **Shared cowork project (claude.ai / Desktop) — rules, triage, drafting,
   collaboration (optional).** Loaded with both Handbooks, the SCED list, the
   runbook, and a **de-identified** error/issue catalog. Used for handbook Q&A,
   error-log triage by category and count, drafting compliance-team handoff
   notes, onboarding, and persisting institutional knowledge. Shareable with the
   compliance team and the state-access uploader.

### PII boundary

This work is PII-dense by nature: resolving a staff combination error requires
name + DOB + SMID together; the student side carries SID + name + DOB. Per
KTAF's data-privacy posture and the project working conventions:

- **Row-level worklists with real names/DOB/IDs stay in BigQuery plus Google
  Sheets** (in-tenant).
- **The cowork project works on rules, error categories/counts, de-identified
  samples, and draft text only** — never pasted rows of identified people.
- The state's returned **error reports likely name records by SID/SMID/name**,
  so they are PII too: the intern resolves errors row-level in the BigQuery
  console / VS Code, and only the de-identified taxonomy (error type, count,
  which query catches it) goes into the cowork project.
- The PII approach for an intern using an external AI tool should get a quick
  sign-off from the data-privacy / People Operations owner; this spec is not the
  final word on that.

## Reference data (setup, in `cokafor`)

| Table                         | Built from                       | Purpose                                                                        |
| ----------------------------- | -------------------------------- | ------------------------------------------------------------------------------ |
| `cokafor.stg_staff_extract`   | loaded Staff CSV                 | the staff extract under audit                                                  |
| `cokafor.stg_student_extract` | loaded Student CSV               | the student extract under audit                                                |
| `cokafor.ref_sced_codes`      | `NJSLEDS_SCED-Course-Codes.xlsx` | valid `SubjectArea` + `CourseIdentifier`, prior-to-secondary vs secondary flag |
| `cokafor.ref_cds_codes`       | literal (below)                  | the valid County/District/School combo per region                              |

`ref_cds_codes` is a two-row literal — KTAF reports each region under a single
County-District-School combo, so there is no statewide CDS file to obtain:

| Region | County | District | School |
| ------ | ------ | -------- | ------ |
| Newark | `80`   | `7325`   | `965`  |
| Camden | `07`   | `1799`   | `111`  |

The CDS check is therefore an **exact-match-per-region** rule with mandatory
leading zeros (`07`, `965`, `111`).

## Audit taxonomy (helper-query catalog)

Each check maps to a Handbook rule, a warehouse source, and a fix-owner. The
queries are organized as a learning ladder (simple filters, then joins, then
`case` logic) and each ships with a plain-English explanation of what it checks
and why.

### Group A — Staff field validity (Staff Course Roster Handbook)

- **1. Missing/invalid SMID** — blank, not exactly 8 digits, or non-numeric.
  Fix-owner: intern (enter once the state issues it) or compliance (generate
  new).
- **2. Combination-error predictor** — the spine of the staff submission. The
  Handbook fails a row unless `LSID` + `SMID` + `FirstName` + `LastName` +
  `DateOfBirth` all match the Staff Management Snapshot exactly, with that
  snapshot record free of Error/Sync/Unresolved. Join the extract to the staff
  source (`int_powerschool__teachers` / Staff Management source) on all five
  fields and flag any mismatch before the state does. Fix-owner: intern (PS
  override fields) or compliance (state SIS for name/DOB).
- **3. Duplicate LSID** — same `LSID` on more than one staff member. Fix-owner:
  intern.
- **4. Name rule violations** — periods or invalid special characters (only
  apostrophes and hyphens are allowed), blanks, or suspected
  nicknames/abbreviations. Fix-owner: intern / People Operations.
- **5. Date validity** — `SectionEntryDate` / `SectionExitDate` in `YYYYMMDD`,
  within the current school year, entry on or before exit, exit not in the
  future. Fix-owner: intern.
- **6. CDS code validity** — `CountyCodeAssigned` / `DistrictCodeAssigned` /
  `SchoolCodeAssigned` exact-match per region against `ref_cds_codes`, leading
  zeros present. Fix-owner: intern.

### Group B — Course/section SCED code validity (Newark + Camden)

This is the "valid sked codes for every course" audit.

- **7. Missing SCED codes** — `SubjectArea` / `CourseIdentifier` / `CourseLevel`
  blank on the course or section. Fix-owner: intern (PS).
- **8. Invalid SCED codes** — not present in `ref_sced_codes`. Fix-owner:
  intern.
- **9. Prior-to-secondary vs secondary consistency** — credit-driven and
  internally consistent: a course with `AvailableCredit` greater than 0 must use
  a secondary code and a populated `AvailableCredit`, with `GradeSpan` blank; a
  course with no credit must use a prior-to-secondary code and a populated
  `GradeSpan`, with `AvailableCredit` blank. Fix-owner: intern.
- **10. Domain checks** — `CourseSequence` in `11`–`99` with the first digit not
  greater than the second; `CourseLevel` in `{B, G, E, H, X}`. Fix-owner:
  intern.

### Group C — Student field validity

- **11. Missing/invalid SID** (`State_StudentNumber`). Fix-owner: intern /
  compliance.
- **12. Same SCED / date / CDS checks** as staff, student-side. The provided
  sample already fails the Newark CDS rule (blank `CountyCodeAssigned`, and
  `SchoolCodeAssigned` of `732` instead of `965`) — a likely section-level CDS
  override gap where PowerSchool falls back to a school's
  `Alternate_School_Number`. Fix-owner: intern (confirm the root cause in PS).

### Group D — Cross-extract parity (the core reconciliation)

- **13. Sections with staff but no students** — PowerSchool junk. Fix-owner:
  intern (fix the source section/enrollment).
- **14. Sections with students but no 100%-allocated teacher.** Fix-owner:
  intern.
- **15. Course/section present in one extract but not the other.** Fix-owner:
  intern.

### Group E — Convergence tracking

- **16. Defect-count rollup** by group, district, and school — re-run each loop
  to watch errors trend toward zero. The de-identified version of this rollup is
  the artifact that feeds the cowork triage project.

### One-time configuration verification (likely N/A for KTAF)

- **Grade-mapping completeness** — confirm every stored-grade code in use has an
  NJ Grade Scale mapping, so no student rows silently drop at the year-end
  extract. This came from PowerSchool's generic documentation, not KTAF
  experience; the sample student extract has blank grade fields (consistent with
  a mid-year extract), and KTAF has not encountered this error. Treated as a
  one-time Phase-0 check, flagged likely N/A. The exact rule is to be confirmed
  against the Student Course Roster Handbook during implementation.

## Timeline and roles

### Roles

- **Intern (`cokafor`)** — runs audits, builds and maintains worklists, fixes
  intern-owned items in PowerSchool (sked codes, staff state-ID override fields,
  SMID entry, duplicate/orphan cleanup), keeps the convergence tracker.
- **Compliance team** — state-side-only actions: generate new SMIDs, push
  name/DOB changes into Staff Management / state SIS, clear Snapshot
  Error/Sync/Unresolved flags.
- **State-access uploader** — uploads the clean extract, returns the error
  report.
- **Data team / owner** — reviews worklists, settles judgment calls, signs off
  the PII approach.

### Phases (about one month)

| Phase                  | Window    | Work                                                                                                                                                       |
| ---------------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0 — Setup              | Week 1    | Provision access; load `ref_sced_codes` + `ref_cds_codes`; load first Camden + Newark extracts; intern SQL/Sheets onboarding; grade-mapping one-time check |
| 1 — Staff + sked codes | Weeks 1–2 | Groups A + B; front-load the compliance handoff (new SMIDs, name/DOB) for maximum lead time before vacations                                               |
| 2 — Student            | Weeks 2–3 | Group C (SID, CDS, dates)                                                                                                                                  |
| 3 — Parity             | Week 3    | Group D orphans/junk                                                                                                                                       |
| 4 — Converge           | Weeks 3–4 | Re-extract, re-run pack, defect rollup to zero, clean files to uploader                                                                                    |
| 5 — State errors       | Week 4+   | Triage returned errors, loop until accepted                                                                                                                |

**Vacation navigation:** identify each role's availability up front; schedule
the handoff-dependent items earliest (compliance-team SMID generation is the
long pole); sequence intern-owned PS fixes so they never block waiting on
someone who is out.

## Deliverables

1. **The runbook** (markdown) — self-sufficient, human-executable, teaches as it
   directs.
2. **The SQL query pack** — documented, console-ready, the learning ladder.
3. **Reference tables** in `cokafor` (`ref_sced_codes`, `ref_cds_codes`, the two
   loaded extracts).
4. **Worklist Sheets** (in-tenant) — one tab per defect group, with status
   dropdowns; the fix-tracker.
5. **Compliance-team handoff sheet** — new-SMID and name/DOB-to-state-SIS items,
   with lead-time dates.
6. **De-identified convergence tracker** — defect counts by group/district/
   school; feeds the cowork triage project and shows errors trending to zero.
7. **The shared cowork project** — handbook knowledge base plus error-triage
   workspace, aggregates/rules only.

## Open items to confirm during implementation

- Confirm the grade-mapping rule against the Student Course Roster Handbook and
  drop the check if it is genuinely N/A for KTAF.
- Confirm the Group C student-side validation specifics (SID format, required
  fields, dropped-course handling) against the Student Course Roster Handbook.
- Confirm the exact staff source model and field names for the combination-error
  predictor join (`int_powerschool__teachers` plus the Staff Management source).
- Confirm the section-level CDS override root cause for the student
  `SchoolCodeAssigned` fallback observed in the sample.
- Confirm whether the intern's VS Code Claude plugin / dev environment will be
  provisioned, or whether Phase 0 should assume the console-only fallback.

## Non-goals

- No dbt models, no post-processing or rewriting of the extract CSV (source-fix
  only).
- No automated/AI-driven classification of defects on the critical path; the
  intern reviews and decides.
- No statewide CDS file ingestion; `ref_cds_codes` is the two-row regional
  literal.
- No row-level PII on any external surface, including the cowork project.
