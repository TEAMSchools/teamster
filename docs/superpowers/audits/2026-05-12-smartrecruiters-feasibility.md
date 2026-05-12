# SmartRecruiters → ADP Associate Crosswalk Feasibility Audit

**Date:** 2026-05-12 **Issue:**
[#3647](https://github.com/TEAMSchools/teamster/issues/3647) **Scope:** Task 5
of the identity-FK-orphans plan — doc-only, no model changes

---

## Background

`dim_job_candidates` and `fct_job_candidate_applications` are built entirely
from SmartRecruiters (SR) data. They carry no FK to `dim_staff_work_assignments`
(ADP) or `dim_staffing_positions` (Seat Tracker). This audit evaluates whether a
SR-candidate → ADP-associate crosswalk is feasible based on available identity
signals in the current warehouse data.

---

## Data Discovery

### SmartRecruiters

- Source model: `stg_smartrecruiters__applications`
  (`kipptaf_smartrecruiters.stg_smartrecruiters__applications`)
- `stg_smartrecruiters__applicants` is **disabled** (`config: enabled: false`) —
  all candidate identity data flows through the applications model.
- Hired-candidate signal: `application_state = 'HIRED'`
- Identity columns available: `candidate_id`, `candidate_email`,
  `candidate_first_name`, `candidate_last_name`, `hired_date`
- Email coverage on hired records: 100% (2,081 hired applications, all with
  email)

### ADP

- Source model: `int_people__staff_roster_history`
  (`kipptaf_people.int_people__staff_roster_history`)
- Key email columns: `work_email` (org-issued only) and `personal_email`
- Name columns: `legal_given_name`, `legal_family_name`
- Hire date: `worker_original_hire_date`

**Critical structural finding:** SR candidates apply with personal/external
emails. ADP `work_email` is exclusively org-issued (kippnj.org, kippmiami.org,
kippteamandfamily.org). Direct work-email matching produces near-zero overlap.
The right join key is `personal_email` on the ADP side.

---

## Email Domain Analysis (SR hired candidates)

| Domain category                             | Count | Share |
| ------------------------------------------- | ----- | ----- |
| gmail.com                                   | 1,474 | 73.0% |
| yahoo.com / hotmail / aol / icloud          | 110   | 5.4%  |
| kippnj.org / kippmiami.org (internal hires) | 95    | 4.7%  |
| Other personal / edu / webmail              | ~341  | 16.9% |

SR applicants use personal addresses throughout the hiring process. Org-issued
KIPP emails appear only for internal re-hires who were already employees.

---

## Match Probes

All counts are at **distinct hired-candidate grain** (n = 2,029 unique
`candidate_id` values across 2,081 hired applications).

### Probe 1 — Work-email match only

Joining `lower(sr.candidate_email)` to `lower(adp.work_email)`:

| Metric                | Count | Rate |
| --------------------- | ----- | ---- |
| SR hired candidates   | 2,029 | —    |
| Matched on work_email | ~78   | 3.8% |

Result: not a viable join key for the general case.

### Probe 2 — Personal-email match

Joining `lower(sr.candidate_email)` to `lower(adp.personal_email)`:

| Metric                    | Count | Rate  |
| ------------------------- | ----- | ----- |
| SR hired candidates       | 2,029 | —     |
| Matched on personal_email | 1,608 | 79.2% |
| Unmatched                 | 421   | 20.8% |

### Probe 3 — Combined email (personal OR work)

| Metric                         | Count      | Rate       |
| ------------------------------ | ---------- | ---------- |
| Matched via personal_email     | 1,608      | 79.2%      |
| Additional via work_email only | ~6         | 0.3%       |
| **Total matched (either)**     | **~1,614** | **~79.5%** |

### Probe 4 — Fuzzy uplift (name + hire-year, unmatched only)

Among the 421 unmatched candidates, joining on
`lower(first_name) = lower(legal_given_name)` AND
`lower(last_name) = lower(legal_family_name)` AND
`ABS(EXTRACT(YEAR FROM hired_date) - EXTRACT(YEAR FROM worker_original_hire_date)) <= 1`:

| Metric                           | Count  | Rate                               |
| -------------------------------- | ------ | ---------------------------------- |
| Unmatched after email probe      | 421    | —                                  |
| Additional fuzzy name+year match | 153    | 36.4% of unmatched                 |
| Estimated combined coverage      | ~1,761 | **~86.8% of all hired candidates** |

Remaining unreachable: ~268 candidates (13.2%). Likely causes: name change after
hire (marriage/legal), email typo in SR, candidates who accepted but never
started, or short-tenure staff not present in the historical roster.

---

## Recommendation

**Build the SR → ADP crosswalk using `personal_email` as the primary join key,
with fuzzy name + hire-year as a fallback.**

Rationale: The personal-email match alone covers 79.2% of hired candidates with
a deterministic, low-false-positive join. Adding the fuzzy name+hire-year
fallback brings estimated coverage to ~87%. This is a sufficient foundation for
linking `dim_job_candidates` / `fct_job_candidate_applications` to
`dim_staff_work_assignments`. The 13% gap is consistent with expected data
quality issues (name change, email drift, pre-start withdrawals) and does not
warrant deferring the crosswalk — it should be treated as a nullable FK with
appropriate `relationships` test configuration.

Implementation notes:

1. The crosswalk should live as an intermediate model (e.g.
   `int_smartrecruiters__candidate_staff_crosswalk`) that produces a
   `(candidate_id, employee_number)` pair using: (a) exact personal-email match,
   (b) fuzzy name+hire-year fallback where (a) fails.
2. `fct_job_candidate_applications` would gain a nullable
   `staff_work_assignment_key` FK via the crosswalk. `dim_job_candidates` would
   gain a nullable `staff_key` (surrogate over `employee_number`).
3. The `personal_email` column on ADP should be validated for completeness
   before building — current probe shows 3,762 distinct personal emails across
   the historical roster, which appears representative but should be confirmed
   against active headcount.
4. `stg_smartrecruiters__applicants` is currently disabled. If reactivating it
   would provide a richer/deduped candidate-email source, that should be
   evaluated as part of implementation.

---

## Artifact Decision

Findings warrant a committed doc (tables, multi-paragraph rationale) rather than
PR-body-only treatment. Placed at
`docs/superpowers/audits/2026-05-12-smartrecruiters-feasibility.md`.

Raw probe detail (domain breakdowns, exact counts before deduplication) retained
in `.claude/scratch/sr-audit.md` (gitignored, not committed).
