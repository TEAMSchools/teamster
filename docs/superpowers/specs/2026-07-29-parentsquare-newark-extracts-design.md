# ParentSquare (KIPP Newark) Outbound Extracts — Design

- **Issue:** [#4480](https://github.com/TEAMSchools/teamster/issues/4480)
- **Asana:** Summer 2027 : SIS Portfolio, task 1216377560708697 (Rebuild Student
  Contacts)
- **Sources of truth:** KIPP NJ + ParentSquare Integration Planner (Google Doc);
  ParentSquare "SFTP Integration" spec (help-center PDF, updated 2026-03-18,
  attached to the Asana task)
- **Status:** phase 0 implemented (see _Implementation notes_ for corrections
  this build made to the design below)
- **Author:** Data Team

## Context

ParentSquare is a family-communications platform. For KIPP Newark it will be
used for **regional mass/emergency communication** to all Newark families (snow
days, emergencies, etc.). Individual schools continue to use DeansList for their
own mass comms — ParentSquare is the regional layer, not a school-messaging
replacement.

It needs a recurring roster feed from the warehouse so the right families and
students are reachable. This is a net-new outbound extract set (no ParentSquare
code exists in the repo) built on the established BigQuery-to-SFTP extract
pattern (`build_bigquery_query_sftp_asset`), the same one behind Clever and the
PowerSchool `autocomm` feeds.

**Scope is KIPP Newark only** for this phase. The Asana task is titled "(NJ)"
and an earlier draft of this spec assumed a network-wide NJ feed, but the
Integration Planner resolves scope to **all Newark schools only** — Camden and
Paterson are not in this phase. Student contacts are sourced from **Finalsite**
(this is the "Rebuild Student Contacts" successor to the Finalsite contact
workstream).

## Goals

- A Newark ParentSquare feed delivering **every file ParentSquare's SFTP spec
  marks required**, plus the optional `emergency_contacts` — seven files:
  `schools`, `students`, `parents`, `staff`, `sections`, `rosters`,
  `emergency_contacts`. See _File set_ below for why this is seven and not the
  four the Integration Planner listed.
- Contacts sourced from Finalsite (Household 1 parents + emergency contacts),
  with stable, mutually consistent record keys across files.
- Build everything that does not depend on the SFTP-credentials blocker now, and
  reconcile once credentials land.

## Non-goals

- **Attendance** — explicitly excluded by the Integration Planner (this is not
  an attendance-notification deployment).
- **Terms (`terms.csv`)** — ParentSquare's spec makes terms required _only if
  terms is enabled_, and it will not be. Consequently `sections.term_id` stays
  empty (the spec makes it required only when sending `terms.csv`), and sections
  carry current-year data rather than full-year.
- **Teacher-classroom rostering** — the Planner sets granularity at school +
  grade level only, so `sections.csv` / `rosters.csv` are satisfied with
  synthetic per-grade sections rather than real course sections. No teacher is
  imported. See _File set_.
- **Any staff beyond the regional Operations leadership** — no school staff, no
  teachers.
- **Parent / student logins** — none needed.
- **Camden, Paterson, Miami** — out of scope for this phase.
- A reusable cross-tool contacts abstraction layer — YAGNI.

## File set

The Integration Planner (question 10) lists four files needed and marks Terms /
Staff / Sections ❌ not needed. ParentSquare's own SFTP spec (page 4) disagrees
— it names seven **required** files:

| ParentSquare spec        | Status                                                 |
| ------------------------ | ------------------------------------------------------ |
| `schools.csv`            | required — built                                       |
| `students.csv`           | required — built                                       |
| `parents.csv`            | required — built                                       |
| `staff.csv`              | required — built (regional Operations leaders only)    |
| `terms.csv`              | required _only if terms is enabled_ — omitted          |
| `sections.csv`           | required — built (synthetic per-grade sections)        |
| `rosters.csv`            | required — built (student → per-grade section)         |
| `emergency_contacts.csv` | **optional** per the spec — built anyway, Ops wants it |

Sending all required files is the decision. The two files the Planner excluded
are therefore built, but shaped so they do not contradict the Planner's other
decisions:

- **`staff.csv` carries only the regional Operations leadership** (question 4:
  "Regional Operation leaders ... No school staff, no teachers"), each emitted
  once per operating school. ParentSquare's staff file is per-school and its
  spec states a staff member may be at more than one, so the fan-out is what
  grants them school-level access everywhere. Membership is the hand-curated
  `TS-DL-Regional Ops Leaders` distribution list scoped to active Newark
  regional-office Operations staff — see _Identifying the Operations leaders_.
- **`sections.csv` holds one synthetic section per (school, grade)**, owned by
  an Operations leader — not real course sections. This is the pattern
  `rpt_clever__sections` already uses for its auto-generated `ENR` sections. It
  satisfies the required file at exactly the granularity question 5 specifies
  ("School + Grade Level only") **without importing a single teacher**, which
  matters because a staff row with an email is synced as a ParentSquare staff
  user — real teacher-led sections would have provisioned accounts for every
  Newark teacher, the opposite of question 4.
- **`rosters.csv` places each student in their (school, grade) section.**

Sections are derived from the (school, grade) pairs students are actually
enrolled in, so no empty section is emitted and every roster row resolves.

### Identifying the Operations leaders

`staff.csv` sources membership from the **`TS-DL-Regional Ops Leaders`** LDAP
distribution list, scoped to active Newark regional-office (`school_id = 0`)
Operations staff. That yields **8** people.

The group is hand-curated — no `idautoGroupIncludeFilter`, no sync interval, so
its membership is set by a human rather than a rule — and it was last modified
2026-06-25, so it is actively maintained. Ops therefore owns this list and role
changes flow through without a code change.

Two alternatives were rejected:

- **A hardcoded list of individuals** matched on KIPP mail. Exactly reproduces
  the six people the Planner names, but rots silently — a new Operations leader
  is absent until someone edits SQL.
- **A `job_function` rule** (`'Chief Level'`, `'KTAF or Regional Director'`,
  `'EDs, HOSs, MDOs'`). Returns exactly the Planner's six today, but only
  because `job_function` is **null** for one Managing Director of School
  Operations who holds the same `job_title` as two included peers.
  `job_function` is null for ~3% of active Newark staff, so that is a data gap
  rather than a signal, and a routine backfill would silently add that person.
  Rejected: the failure mode is silent over-provisioning.

The group yields two people the Planner's list of six does not name — a Deputy
Chief and the Managing Director of School Operations mentioned above. Both are
in the curated leaders list AND in the automated
`TS-SG-Okta Parentsquare All Ops` group, so both are plausibly intended; the
MDSO especially, given the shared title. Confirm with Ops (see _Open
questions_).

For contrast, `TS-SG-Okta Parentsquare All Ops` — despite its name — is not
usable here. It is idauto rule-generated (4-hour sync) and resolves to all 12
regional Operations staff at the same scoping, including Facilities Managers;
without the `school_id = 0` filter it reaches 124 Newark staff, 88 of them
school-based, which squarely contradicts "no school staff". It governs app SSO,
not the roster feed.

## Approach

Follow the Clever precedent. A set of `rpt_parentsquare__*` reporting views in
the `kipptaf` dbt project, filtered to Newark, each serialized to a CSV and
pushed to a new `parentsquare` SFTP destination by the generic extract factory.
Files are full snapshots each run; ParentSquare reconciles adds/changes/removals
on its side (its docs note attendance/data diffs are handled automatically, and
the roster files are re-read each sync).

## Components

1. **dbt models** — `src/dbt/kipptaf/models/extracts/parentsquare/`, one
   `rpt_parentsquare__<file>.sql` per file (schools, students, parents,
   emergency_contacts, staff, sections, rosters) plus a `properties/` YAML with
   contract, uniqueness, and cross-file `relationships` tests. Land in
   `kipptaf_extracts` (view, contract-enforced by directory default).

1. **Extract config** —
   `src/teamster/code_locations/kipptaf/extracts/config/parentsquare.yaml`, one
   asset block per file, wired in `kipptaf/extracts/assets.py` with
   `destination_config={"name": "parentsquare"}` (the `clever_extract_assets`
   list-comprehension pattern). File stems must be the exact ParentSquare names
   (`schools`, `students`, `parents`, `emergency_contacts`, `staff`, `sections`,
   `rosters`), suffix `csv`, header row on.

1. **Destination resource** — `SSH_RESOURCE_PARENTSQUARE` (`SSHResource`, host
   `sftp3.parentsquare.com`) in `kipptaf/resources.py` (not `core/resources.py`
   — every other kipptaf-only SFTP destination lives there), wired as
   `ssh_parentsquare` into `kipptaf/definitions.py`. All three variables are
   mapped to the `op-parentsquare-sftp` Secret at both `dagster-cloud.yaml`
   insertion points; see _Credential wiring_.

1. **Job + schedule** — `kipptaf__extracts__parentsquare__asset_job` in
   `extracts/jobs.py`, plus a daily `ScheduleDefinition` in
   `extracts/schedules.py`. ParentSquare recommends sending in the **early
   evening**, so schedule ~6-7pm ET (not the 3am roster slot). Shipped paused
   until the round-trip is verified.

1. ~~**Exposure** — dbt exposure in `src/dbt/kipptaf/models/exposures/`.~~ Not
   built: no SFTP extract feed in this repo has one (clever, illuminate, idauto,
   coupa, egencia all lack them), and the Dagster extract asset already carries
   the lineage. See _Implementation notes_.

## Data flow

Each model reads existing network models, filters to Newark
(`_dbt_source_project = 'kippnewark'` /
`_dbt_source_relation like '%kippnewark%'`), and projects the ParentSquare
columns.

| File                 | Source                                                                                 | Key                                                                   |
| -------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `schools`            | `stg_powerschool__schools` (Newark; `state_excludefromreporting = 0`)                  | `school_id = school_number`                                           |
| `students`           | `int_extracts__student_enrollments` (Newark, current academic year, active enrollment) | `student_id = student_number`                                         |
| `parents`            | `int_students__contacts` where `contact_slot in ('contact_1', 'contact_2')`            | linked by `student_id`; no `parent_id`                                |
| `emergency_contacts` | `int_students__contacts` where `contact_slot like 'emergency_%'`                       | `contact_id = generate_surrogate_key([student_number, contact_slot])` |
| `staff`              | `TS-DL-Regional Ops Leaders` LDAP group joined to the roster, crossed with schools     | `staff_id = employee_number`; one row per (leader, school)            |
| `sections`           | distinct (school, grade) from `int_extracts__student_enrollments`                      | `section_id = school_number + zero-padded grade`                      |
| `rosters`            | `int_extracts__student_enrollments` (same filter as `students`)                        | `(section_id, student_id)`                                            |

Every cross-file reference is enforced by a `relationships` test rather than
assumed — `students`/`staff`/`sections`/`rosters` all point at
`schools.school_id`, `rosters` points at both `sections.section_id` and
`students.student_id`, and `sections.staff_id` points at `staff.staff_id`.

### Contacts sourcing (Finalsite)

`int_students__contacts` is the unified long contacts model, one row per
`(student, contact_slot)`. Newark contacts resolve through its **Finalsite**
branch, so `finalsite_contact_id`, `is_household_member`, and `is_emergency` are
populated. It exposes `contact_name`, `relationship`, `email_current`,
`phone_mobile/home/daytime/work/primary`, and `address_home`.

- **`parents.csv`** = the household parent slots `contact_1` + `contact_2`
  (Planner: "Finalsite Household 1 AND Parent 1 AND Parent 2"). One row per
  parent; the format supports more than two if a household ever has them.
  ParentSquare requires **email OR mobile** per parent — drop rows with neither.
- **`emergency_contacts.csv`** = the `emergency_1`..`emergency_4` slots. These
  are scalar custom fields on the student's OWN Finalsite record, not linked
  contact records, so `int_finalsite__student_contacts` sets
  `finalsite_contact_id` to explicit NULL for every emergency row — the required
  `contact_id` is therefore
  `generate_surrogate_key([student_number, contact_slot])`, unique per (student,
  emergency ordinal). Requires **email OR phone**; emergency contacts receive
  only Smart/Urgent Alerts and get no ParentSquare account.

### ID consistency and formatting

Keys are SIS-native and consistent across files: `student_id = student_number`,
`school_id = school_number`. Per the ParentSquare spec, IDs must be one
continuous string, no spaces, and `school_id` allows no spaces/underscores/
periods; all fields ingest as strings; header names must match exactly
(underscores, no spaces/dashes); phones are 10 digits.

`grade_level` must land on ParentSquare's **-4..12** scale (K = 0, PreK1 = -4,
PreK2 = -3, Junior K = -2, Transitional K = -1). Newark's current-year
`grade_level` domain is `0`..`12`, which already satisfies that scale, so the
feed casts the value through unchanged and needs no mapping table. A PreK grade
would need one; Newark operates none today.

## File specs (from the ParentSquare SFTP PDF)

All seven files sent. `Yes*` = one of email/phone required.

- **`schools.csv`** — `school_id`, `school_name`, `school_zip`,
  `school_address`, `school_city`, `school_state`, `principal_first_name`,
  `principal_last_name`, `principal_email`, `school_phone` (all required).
- **`students.csv`** — required: `school_id`, `student_id`, `first_name`,
  `last_name`, `grade_level`. Optional: `state_student_id`, `status` (1 =
  active, 0 = incoming), `student_email`, `cellphone` (10 digits).
- **`parents.csv`** — required: `school_id`, `student_id`, `first_name`,
  `last_name`, and email OR mobile. Optional: `parent_id` (unused),
  `relationship`, `language`, `secondary_phone`.
- **`emergency_contacts.csv`** — required: `school_id`, `student_id`,
  `contact_id`, `first_name`, `last_name`, and email OR phone.
- **`staff.csv`** — required: `school_id`, `staff_id` (unique to the staff
  member, but the member may be at more than one school; cannot be shared with
  another staff user), `first_name`, `last_name`, and email OR mobile (`email`
  and `mobile` are each flagged unique). Optional: `title`, `login`,
  `secondary_phone`. This feed emits `school_id`, `staff_id`, `first_name`,
  `last_name`, `email`, `title` — no phone, so `email` is the only
  deliverability field and is tested `not_null` at error.
- **`sections.csv`** — required: `school_id`, `section_id` (no spaces or
  periods; may repeat to support co-teachers), `staff_id`, `course_name`.
  Optional: `term_id` (required only if sending `terms.csv`), `period_number`,
  `section_number`, `is_primary` (1 = primary teacher, 0 = co-teacher; only one
  primary per section). This feed emits everything except `term_id` and
  `period_number`.
- **`rosters.csv`** — required: `school_id`, `section_id` (no spaces or
  periods), `student_id`. All three are emitted; there are no optional columns.

## Delivery

- Server `sftp3.parentsquare.com`, **district-level single connection** (one set
  of files covering all Newark schools). Password or SSH key — created in the
  ParentSquare admin UI, which issues the username.
- Header row required; exact ParentSquare filenames; CSV; all values strings.
- Send in the early evening; the schedule ships paused until verified.
- Firewall note: if outbound SFTP is IP-restricted, ParentSquare's egress IPs
  are documented in the spec (not expected to matter for Dagster's egress).

## Sequencing around the blocker

1. **Phase 0 — now, unblocked.** Build the seven `rpt_parentsquare__*` models
   with properties/tests, the `parentsquare.yaml` config, the `ssh_parentsquare`
   resource class, and the paused job + schedule. The `dagster-cloud.yaml`
   variable mappings are deliberately NOT part of this phase — see
   _Implementation notes_. Validate model SQL and the asset graph in a branch
   deployment against `teamster-test`.

1. ~~**Blocker — SFTP credentials.**~~ CLEARED. The credential is in 1Password
   as **ParentSquare SFTP**, and the `OnePasswordItem` plus all four
   `dagster-cloud.yaml` mappings are in this branch — see _Credential wiring_
   for the two steps that must precede a deploy (apply the item, confirm the key
   names). Still outstanding from this step: confirm the upload path, and verify
   a one-file round-trip before sending all seven.

1. **Phase Final.** Un-pause the schedule, confirm ParentSquare ingests the
   files cleanly, hand off to Ops.

## Implementation notes

Corrections and decisions from the phase-0 build. Where these conflict with the
design above, these win.

### `int_students__contacts` gained first/last name columns

ParentSquare requires `first_name` and `last_name` as discrete fields, and
`int_students__contacts` exposed only the combined `contact_name`. Rather than
split that string — wrong for the ~4% of Newark contacts with 3+ name tokens,
where a compound first name and a multi-word surname are indistinguishable — the
model now carries `contact_first_name` / `contact_last_name`. Both branches
supply them natively: Finalsite from `int_finalsite__student_contacts`
(`contact_first_name` / `contact_last_name`, populated for parents AND emergency
slots), PowerSchool from `int_powerschool__contacts` (`firstname` / `lastname`).
Purely additive — `int_students__contacts_pivot`, `rpt_clever__students`,
`bridge_student_contacts`, and `dim_student_contact_persons` all enumerate
columns explicitly and are unaffected.

### Principal names come from the staff roster, not the PowerSchool string

`stg_powerschool__schools` holds one combined `principal` field that also
carries honorifics, so `rpt_parentsquare__schools` resolves the name pair from
`int_people__staff_roster` on `lower(principalemail) = lower(mail)`. All 12
reporting Newark schools match, `mail` is unique on the roster so the join
cannot fan out, and the one honorific-bearing value resolves correctly.

### Credential wiring

The credential landed in 1Password as **ParentSquare SFTP** (Data Team vault),
so the mappings this design originally deferred are now in place:

- `.k8s/1password/items.yaml` gains a `OnePasswordItem` named
  `op-parentsquare-sftp` pointing at `vaults/Data Team/items/ParentSquare SFTP`,
  which is what creates the k8s Secret.
- `dagster-cloud.yaml` maps `PARENTSQUARE_SFTP_HOST` / `_USERNAME` / `_PASSWORD`
  at all four insertion points — the credentials and host blocks of both
  `server_k8s_config` and `run_k8s_config`. `EnvVar` resolves in both places
  under `k8s_job_executor`, so omitting either half breaks one of them.

**Two ordering constraints, both load-bearing.** A `secretKeyRef` naming a
Secret or key that does not exist fails container creation for the whole
`kipptaf` code server — not just this feed — so before any deploy carrying these
mappings:

1. The `OnePasswordItem` must be applied to the cluster (`kubectl apply`), which
   is what materializes the Secret. It is not applied by CI. **Done.**
1. The key names must be read off the synced Secret rather than assumed. k8s
   Secret keys come from the 1Password field's **internal** name, not the UI
   label. **Verified** —
   `kubectl -n dagster-cloud get secret op-parentsquare-sftp -o jsonpath='{.data}' | jq keys`
   returns `["URL", "password", "username"]`, so the mappings are:

   | Variable                     | Secret key |
   | ---------------------------- | ---------- |
   | `PARENTSQUARE_SFTP_HOST`     | `URL`      |
   | `PARENTSQUARE_SFTP_USERNAME` | `username` |
   | `PARENTSQUARE_SFTP_PASSWORD` | `password` |

   The host field is the documented remap case and it bit here: `host` was the
   natural guess and is wrong. Note the capitalization is item-specific too —
   `op-couchdrop-sftp` uses `URL` but `op-lattice-sftp` uses lowercase `url`, so
   neither the name nor its case generalizes. A `secretKeyRef` to a missing
   **key** fails container creation exactly as a missing Secret does.

The schedule stays stopped regardless — wiring the credential does not imply the
round-trip has been verified.

### Phone numbers are validated to exactly 10 digits

ParentSquare requires 10-digit phones. Both contact models strip formatting,
drop a leading US country code, truncate to 10, and then null anything that is
not exactly 10 digits rather than send a number ParentSquare would reject along
with the rest of the row. This drops 6 emergency-contact rows whose only phone
is a 9-digit typo and which carry no email — an upstream Finalsite data-entry
fix for Ops, not a modelling problem.

### No exposure

Every SFTP extract feed in the repo omits one and the extract asset already
depends on the dbt model's asset key, so lineage is intact. Adding a lone
`sftp.yml` exposure for ParentSquare would be inconsistent with clever,
illuminate, idauto, coupa, and egencia.

### Verified output (current academic year, prod data)

| File                 | Rows   |
| -------------------- | ------ |
| `schools`            | 12     |
| `students`           | 6,796  |
| `parents`            | 9,259  |
| `emergency_contacts` | 15,399 |
| `staff`              | 96     |
| `sections`           | 53     |
| `rosters`            | 6,796  |

`staff` is 8 leaders × 12 schools with no missing email, first name, or last
name — re-measured after the group refactor, not carried over from the earlier
hardcoded six. `sections` is 53 distinct (school, grade) pairs; every
`section_id` is unique, at most 11 characters, and free of spaces and periods.
`rosters` is one row per student.

Referential integrity holds in both directions across the whole set — no orphan
`school_id`, `student_id`, `section_id`, or `staff_id`; no section without
students; no student without a roster row. No contact row lacks both email and
phone, no phone is other than 10 digits, every school has a resolved principal
name, and `state_student_id` / `student_email` are unique as ParentSquare's spec
requires. The `state_excludefromreporting = 0` filter yields exactly the 12
schools Newark students actually attend.

## Open questions

1. **Newark-only phase 1** — confirmed by the Integration Planner; flagging
   because it overrides the task's "(NJ)" title. (Issue #4480 corrected to
   match.)
1. ~~**Reduced file set**~~ — RESOLVED by sending all of them. The spec's page-4
   list is `schools`/`students`/`parents`/`staff`/`terms`/`sections`/`rosters`,
   with `terms` conditional on terms being enabled and `emergency_contacts`
   actually **optional**. All required files are now built; see _File set_.
1. **SFTP credentials + upload path** — pending app access; also confirm whether
   files land at the SFTP root or a subdirectory. The config currently sets no
   `destination_config.path`, so files land at the connection's home directory;
   add a relative `path` if ParentSquare wants a subdirectory.
1. ~~**`grade_level` mapping**~~ — RESOLVED: Newark's grade domain is `0`..`12`,
   which already matches ParentSquare's scale, so no mapping is needed.
1. ~~**Parents scope**~~ — RESOLVED: the Planner's question 6 answers "Parent 1,
   Parent 2", matching `contact_1` + `contact_2`. Note the Planner also says
   "Link student ID to as many as parents (can be unlimited)"; that describes
   ParentSquare's file capability, and is moot today because
   `int_finalsite__student_contacts` produces at most two parent slots by
   construction. Lifting the cap would be an upstream change to the
   household-membership logic, not to `rpt_parentsquare__parents`.
1. ~~**Staff phase 2**~~ — RESOLVED: `staff.csv` is built now, scoped to the
   `TS-DL-Regional Ops Leaders` group. Members are emitted per operating school
   rather than at `school_id = 0`, because the schools feed carries no
   district-office row.
1. **Two leaders beyond the Planner's list** — scoping the group to Newark
   regional Operations yields 8, where the Planner's question 4 names 6. The
   extras are a Deputy Chief and a Managing Director of School Operations.
   Confirm with Ops that both should have ParentSquare access; if not, they
   should be removed from `TS-DL-Regional Ops Leaders` (or a dedicated
   ParentSquare group created) rather than filtered in SQL, so the list stays
   Ops-owned.
1. **Teacher accounts** — the synthetic per-grade sections deliberately avoid
   importing teachers, since a staff row with an email becomes a ParentSquare
   staff user. Confirm with Ops before un-pausing that grade-level sections
   owned by an Operations leader give them the audiences they expect, and that
   no school staff are expected to post.
1. **Section ownership churn** — the section owner is picked as the lowest
   `staff_id` among the leaders — lexicographically lowest, since `staff_id` is
   the string form of `employee_number`; which leader it selects does not
   matter, only that it is stable. If that person leaves, `sections.staff_id`
   changes and ParentSquare may re-create the sections. Acceptable for phase 1;
   revisit if it causes churn.

## Testing and validation

- **dbt:** contract enforcement plus a uniqueness test per model — `school_id`
  for schools, `student_id` for students, `section_id` for sections,
  `contact_id` for emergency contacts, `(student_id, first_name, last_name)` for
  parents, `(section_id, student_id)` for rosters, `(school_id, staff_id)` for
  staff. Every key and cross-file `relationships` test carries
  `severity: error`, including the `not_null` on each FK column — dbt's
  `relationships` test filters nulls out of the child side, so a null FK would
  otherwise pass it vacuously.
- **Cross-file integrity:** `students`/`staff`/`sections`/`rosters` →
  `schools.school_id`; `rosters` → `sections.section_id` and
  `students.student_id`; `sections.staff_id` → `staff.staff_id`. Plus a
  reverse-direction singular test that every `students.student_id` appears in
  `rosters` — `relationships` only covers child→parent, so nothing else catches
  a student who reaches the feed with no grade-level section and therefore lands
  in no audience.
- **Domain:** `grade_level` is asserted against ParentSquare's `-4`..`12` scale
  at error severity, rather than relying on Newark's current domain staying
  inside it.
- **Asset graph:** targeted import / `dagster definitions validate` for the
  extended `kipptaf` extracts wiring.
- **Round-trip:** in a branch deployment, deliver one file to the ParentSquare
  SFTP first, confirm it lands and parses, then enable all seven.
- **Vendor ingest:** with Ops, confirm ParentSquare ingests each file without
  id/match errors before un-pausing.

## PII

These files carry student and guardian PII (names, contact info). Delivery is
SFTP-to-vendor only; no PII values go to the issue, PR, Asana, or any external
surface, and validation output stays local. Tag PII columns per the repo's
`config.meta.contains_pii` convention.

## References

- Extract factory: `src/teamster/libraries/extracts/assets.py` (+ its
  CLAUDE.md).
- Clever analog: `src/dbt/kipptaf/models/extracts/clever/rpt_clever__*.sql`;
  config `.../extracts/config/clever.yaml`.
- Contacts source: `int_students__contacts` (Finalsite branch),
  `int_finalsite__student_contacts`, `int_finalsite__contact_id_attributes`.
- Destination-resource pattern: `SSH_*` resources in
  `src/teamster/core/resources.py`.
