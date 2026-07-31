# Focus CONTACTS — address resolution and emergency contacts

Design for [#4651](https://github.com/TEAMSchools/teamster/issues/4651) (fix)
and [#4652](https://github.com/TEAMSchools/teamster/issues/4652) (feature). Both
edit `rpt_focus__contacts`, so #4651 lands first and #4652 stacks on it.

Continues the work of
[#4613](https://github.com/TEAMSchools/teamster/issues/4613) /
[PR #4618](https://github.com/TEAMSchools/teamster/pull/4618), which resolved
the same arbitrary-household defect for the Focus `ADDRESS` feed.

All figures below were measured against production on 2026-07-31, over the
1,505-student / 2,601-row enrolled Miami CONTACT feed.

## Problem

`rpt_focus__contacts` projects each guardian's address from
`stg_finalsite__contacts`, whose scalar `address_*` columns flatten
`households[safe_offset(0)]`. Array position does not identify Finalsite's
primary household — that designation is set in the UI and exposed by no API
field. Whichever household sits at offset 0 becomes the contact's address in
Focus.

The feed is import-once with no overwrite path, so a wrong pick is permanent.
Only 13 students currently have a person record in Focus, so ~99% of the
population is still prospective — the same posture the `ADDRESS` fix had.

Separately, Finalsite emergency contacts never reach the feed at all. They are
custom fields on the student's own contact record (`emrg_1..4_*`), not
relationship rows, so the adult-relationship-type filter cannot see them. Four
Focus layout columns are hardcoded null in consequence.

## Decisions

### The CONTACT address resolves from the guardian's own household linkage

Rejected: inheriting the student's resolved address of record, and omitting the
address entirely. Measured comparison, over 2,601 rows:

| Option                               | Rows with an address | Values changed | Newly enabled | Newly withheld |
| ------------------------------------ | -------------------- | -------------- | ------------- | -------------- |
| Today (`households[safe_offset(0)]`) | 2,465                | —              | —             | —              |
| Guardian's own linkage               | 2,071                | 0              | 42            | 436            |
| Student's address of record          | 2,197                | 66             | 53            | 321            |
| Omit entirely                        | 0                    | —              | —             | 2,465          |

Two measurements decided it. Anchoring on the guardian changes **zero** existing
address values — whenever a guardian's linkage resolves to exactly one distinct
complete address, offset 0 already equals it, so the entire effect is
withholding rows that are currently coin flips. And where the guardian's own
linkage and the student's address of record both resolve, they **agree on 1,961
rows and disagree on 12** — the cross-feed inconsistency #4651 describes is a
12-row problem, not a systemic one, and does not justify asserting that a
guardian lives where the student lives.

Unlike the `ADDRESS` feed, an unresolved guardian keeps their row and gets a
null address. The CONTACT row still carries the name, relationship, email, and
phones, which are the reason the record exists.

### Address identity: street-present filter, normalized five-field key

The candidate filter is `address_1 is not null`, replacing
`is_complete_address`. Withholding on incompleteness is dropped: an incomplete
address should reach Focus and be corrected by consumers, since an incomplete
address is visibly wrong in a way a wrongly-picked complete address is not.

Removing the filter entirely is worse, not better. 94 Miami households carry a
city/state/ZIP fragment with no street; each would count as a distinct candidate
and manufacture ambiguity that is not real, dropping resolution to 2,024 rows.
Exactly 1 household has a street but is incomplete, so the filter swap admits
one extra household today and changes the rule for future data.

Address identity is all five mailing fields compared case- and
punctuation-insensitively with ZIP truncated to 5. Normalization applies to
**grouping only** — the address projected to Focus is the raw values from the
lowest-`household_id` row of the group, so Focus receives properly formatted
text.

Loosening the key to `address_1` alone was rejected. The two changes price
separately:

| Rule                           | CONTACT rows | Delta | What the delta is                       |
| ------------------------------ | ------------ | ----- | --------------------------------------- |
| Five-field key, raw comparison | 2,071        | —     | baseline                                |
| Five-field key, normalized     | 2,081        | +10   | formatting-only merges — same address   |
| `address_1` key, normalized    | 2,093        | +12   | genuinely different addresses collapsed |

The 12 rows the `address_1` key buys come from 8 guardians: **5 differ by
city**, 2 by apartment number, 1 by ZIP. Collapsing them means choosing a
household by `household_id` order — a stable but meaningless ordering, the same
class of defect as `safe_offset(0)`. Only 1 of the 8 (apartment vs. blank
apartment) is plausibly one address recorded twice.

The asymmetry that settles it: an incomplete address in Focus is detectable by a
human, so the "consumers correct it" mechanism works. A wrongly-picked complete
address looks correct and is permanent, so it does not.

Net effect of the chosen rule: CONTACT 2,081 rows with an address, ADDRESS 1,270
students (up from 1,264), and **zero exported address values change on either
feed**.

### Emergency rows append after guardians, ordered by slot

`emrg_N_priority_ss` is null for all 6,405 Miami contacts, so interleaving by
priority has nothing to sort on and every row would fall through to a slot
tiebreak anyway. Guardians keep ranks 1..N in their existing order; emergency
slots follow in `emrg_1..4` order.

### Guardian rows keep null custody / pickup / resides-with flags

The relationship grain carries no equivalent fields. Import-once makes a blanket
assumption permanent and unfixable from the pipeline, and Focus treats null as
"not asserted" rather than "no". Only `emergency` gets a value, and only on
emergency-slot rows.

### Emergency rows that name-match a guardian are still sent

61 of the 923 emergency rows name-match a guardian row for the same student.
Both are sent. The two rows carry different data — the guardian row has the
relationship and household address, the emergency row has up to three typed
phones and the emergency designation. Suppressing by name match is a fuzzy
identity test that would drop the emergency flag for exactly the people most
likely to be the emergency contact.

### Pickup-only and barred-pickup blocks are out of scope

`pickup_1..3_*` and `nonpickup_1..3_*` are name-only — no phone, no
relationship, no email. A pickup-only row would create a permanent Focus person
record carrying nothing but a name. `nonpickup` names people **barred** from
pickup, and the Focus `CONTACTS` layout has no way to express that, so importing
them as contacts would invert their meaning.

## Design — #4651

### `int_finalsite__contact_address_of_record` (new)

`src/dbt/finalsite/models/api/intermediate/`. One row per Finalsite contact.
Applies the resolution rule above at contact grain — the same rule
`int_finalsite__student_address_of_record` applies, without the student-specific
primary-contact fallback.

1. Read `int_finalsite__contacts__households` where `address_1 is not null`.
1. Derive the normalized grouping key as named columns in a CTE (uppercased,
   non-alphanumerics stripped from `address_1` / `address_2`, uppercased `city`,
   `state`, `left(zip, 5)`) — not inline, so the `dbt_utils.deduplicate` call
   partitions on plain columns.
1. Dedupe to one row per (contact, distinct address) with
   `dbt_utils.deduplicate`, `order_by="household_id asc"`, so `country` and the
   raw address values come from one canonical row rather than being blended
   across households.
1. Count candidates per contact.
1. Project the address only when the count is exactly 1.

Columns: `finalsite_enrollment_id`, the five address fields, `country`,
`candidate_count`, `is_complete_address`, and `resolution_status` (`resolved` /
`ambiguous` / `no_street`).

Not contract-enforced (the `api/intermediate` directory default), but every
column carries a `data_type` per convention. Uniqueness test on
`finalsite_enrollment_id`.

### `int_finalsite__student_address_of_record` (refactor)

Its `complete_households` / `address_candidates` / `candidate_counts` CTEs are
replaced by two joins to the new model — once on the student's id, once on the
primary contact's. The student-first-then-primary-contact pick, the
`address_source` / `resolution_status` outputs, and the `primary_contact_phone`
passthrough are unchanged.

This refactor is required rather than cosmetic: if the identity rule normalized
for contacts but not for students, the two feeds would resolve addresses by
different rules again, which is the defect #4651 exists to close.

### kipptaf wiring

Add `int_finalsite__contact_address_of_record` to the four
`kipptaf/models/finalsite/sources-kipp*.yml` files (the `zz_stg_` staging branch
is already present on all four), and add a `union_relations` passthrough at
`kipptaf/models/finalsite/intermediate/`, following
`int_finalsite__student_address_of_record` — all four regions unioned, since the
`rpt_focus__*` filter on `focus_student_id_prefixed is not null` keeps non-Miami
rows out of the Focus feeds.

### `rpt_focus__contacts`

Replace `g.address_1 … g.zip` with the resolved columns, `left join`ed on the
guardian's `finalsite_enrollment_id`. The relationship-type filter, the three
gating joins, `sort_order`, and the 50-column contract are untouched.

## Design — #4652

### Structure

Three CTEs plus a final projection:

- `guardians` — the #4651 query, plus `0 as contact_group` and
  `if(is_primary, 0, 1) as group_rank`. The `row_number()` moves out.
- `emergency_long` — four `union all` branches over
  `int_finalsite__contact_custom_attributes`, one per `emrg_N`, each gated
  `emrg_N_name_first_name is not null and emrg_N_name_first_name != ''`. Carries
  `1 as contact_group` and `N as group_rank`. Transfers the shape from
  `int_finalsite__student_contacts`, which cannot be `ref`'d here — it excludes
  Miami to avoid double-counting against the PowerSchool branch of
  `int_students__contacts`.
- `all_contacts` — the union, with a single
  `row_number() over (partition by student_id order by contact_group, group_rank, last_name, first_name, relationship_id)`
  as `sort_order`.

`relationship_id` is a new final tiebreak. Today two guardians sharing
`(is_primary, last_name, first_name)` get a rank that can flip between runs;
making it stable is free.

`dbt_utils.unique_combination_of_columns(student_id, sort_order)` holds by
construction — one `row_number()` over one partition — and stays as-is.

### Emergency row column mapping

| Focus column                                | Source                                                      |
| ------------------------------------------- | ----------------------------------------------------------- |
| `student_relation`                          | `coalesce(emrg_N_relationship_ss, emrg_N_relationship_txt)` |
| `first_name` / `last_name`                  | `emrg_N_name_first_name` / `_last_name`                     |
| `middle_name`                               | `emrg_N_name_middle_name` for slots 1–2; null for 3–4       |
| `emergency`                                 | `'Y'`                                                       |
| `custody`                                   | `if(emrg_N_custody_yn, 'Y', null)`                          |
| `resides_with_stud`                         | `if(emrg_N_lives_with_yn, 'Y', null)`                       |
| `pickup`                                    | `if(emrg_N_pickup_yn, 'Y', null)`                           |
| `email`                                     | `emrg_N_email`                                              |
| `contact1_*` / `contact2_*` / `contact3_*`  | `emrg_N_phone_1..3_type` and `_number`                      |
| address / address2 / city / state / zipcode | null — emergency contacts carry no household linkage        |
| `contact4_*`–`contact7_*`, all flag columns | null, unchanged                                             |

The pivot has no middle-name field for slots 3 and 4, hence the split. Guardian
rows keep `contact3_*` null; extending them to a third phone is out of scope.

### Two assumptions on the record

`'Y'` or null, never `'N'`. Focus's `students_join_people` holds only `'Y'` and
null across its 22 existing rows, so an explicitly-false Finalsite flag maps to
null. Worth an Ops confirmation, not a blocker.

Miami ships three of the four columns still null. `emrg_N_custody_yn`,
`_pickup_yn`, `_lives_with_yn`, and `_priority_ss` are **100% null across all
6,405 Miami contacts**. They are well populated in Newark (6,916 of 6,923),
Camden, and Paterson — but Miami is the only Focus region. The mapping is wired
correctly and populates the moment Miami's form collects the fields.

### Scale and the import-once ceiling

923 emergency rows across 464 students join the 2,601 guardian rows. `emrg_3`
and `emrg_4` are unpopulated in Miami but populated in all three NJ regions, so
all four slots are built.

The kippmiami wrapper's anti-join is on `student_id`, not on the contact — once
a student has any person in Focus, none of their contacts ever flow again. Today
that is 13 students, so emergency rows reach essentially the whole population.
Every student imported before this ships permanently loses their emergency
contacts, which argues for landing both branches promptly and needs a line in
the ops doc.

## Rollout

Worktree off `main` for #4651; #4652 stacked on it via
`gh issue develop 4652 --base <branch-1>`. Branch 2's PR will not get
`claude-review` (it fires only on a `main` base) and cannot merge until branch 1
does.

The new model is new, so `dbt clone` cannot seed it — it is absent from the prod
manifest and gets skipped silently. Each district needs a real
`dbt build --select int_finalsite__contact_address_of_record --target staging --project-dir src/dbt/<district>`
before push, or kipptaf CI cannot resolve the union's column list. That writes
to shared `zz_stg_*` datasets and needs explicit user authorization naming the
operation.

The `int_finalsite__student_address_of_record` refactor needs no re-staging —
same column set, values only.

Editing four `sources-kipp*.yml` marks the whole finalsite source
`state:modified`, so CI fans out across every kipptaf model reading finalsite.
Expect the wide run PR #4618 saw; pre-existing warn-test noise is pre-existing.

## Validation

Both feeds are import-once, so everything is validated against production before
either PR leaves draft.

- Refactor parity — `int_finalsite__student_address_of_record` dev vs prod:
  identical row count and identical `format('%T', ...)` tuple set except exactly
  the 6 newly-resolving students. Any other delta is a refactor bug.
- CONTACT feed — 2,601 rows, 2,081 with an address, 0 changed values against the
  current prod feed; on branch 2, 923 emergency rows across 464 students.
- Grain — `unique_combination_of_columns(student_id, sort_order)` on the built
  model, not on paper.
- Unit tests — the whole `test_type:unit,extracts.focus` directory, since
  sibling Focus models mock the same refs. Both new inputs must use
  `format: sql`; `int_finalsite__contact_address_of_record` will not exist in
  the warehouse when the unit test compiles, so dict-format `given` rows fail
  introspection.
- `trunk check --force` from inside the worktree on every changed SQL and YAML.

## Documentation

`docs/reference/finalsite-focus-import.md` gains the CONTACT address behavior
and the emergency-contact rows. Its existing claim that a student's address is
held back when incomplete no longer holds for contacts, and the
`rpt_focus__addresses` inline comment asserting that
`address_source is not null` guarantees a complete address becomes false — both
are corrected.

## Deliberately not in scope

- Duplicate Finalsite households, the cause of the ~205 unresolvable Miami
  guardians. Retiring them is Miami ops work.
- Asserting the `is_primary` singleton at its source
  ([#4616](https://github.com/TEAMSchools/teamster/issues/4616)) and students
  with no `primary` relationship
  ([#4617](https://github.com/TEAMSchools/teamster/issues/4617)).
- A third phone slot for guardian rows.
- An Ops-facing surface listing unresolvable duplicate households.
