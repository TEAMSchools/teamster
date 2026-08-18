# NJ ISR distribution — design

Refs #4915

## Problem

For NJ state reporting each region is a single LEA and a single school. The LEA
and the school are coterminous, so the state ships one alphabetized run of
individual student reports (ISRs) per region with no campus-level field anywhere
in it. Spring 2026 NJGPA for Newark is 299 reports under one school code; NJSLA
across grades 3-9 will be roughly twenty times that volume across more subjects
and more files.

Reports must reach students within approximately 30 days of receipt, while
enrollment is still churning.

The prior process split the vendor PDF and re-merged it into one large PDF per
campus, keyed on current-year enrollment at sort time. Three failures followed:

- A no-show rollback moved a student back to their previous campus _after_ their
  report had already been sorted to the new one. The previous campus could not
  find it and did not check the overflow folder.
- The merged PDFs ran to hundreds of MB, so retrieving one student meant
  downloading the whole file.
- Unmatched reports landed in a passive overflow folder with no owner.

The root error was making one artifact serve both a hard-deadline compliance
event and a year-long lookup service. Those have different keys, different
lifetimes, and different failure modes.

## Format findings

The vendor changed from Pearson to Cambium for Spring 2026. Findings below are
measured from the NJGPA ISR PDF and both district manifests; the working
analysis and scripts live in `.claude/scratch/NJ ISRs/analysis/` (gitignored,
contains live PII).

### The record boundary is a structural footer token

Every page carries a footer of the form:

```text
<district>.<district>_<school>.<record_seq>
7325.7325_965.1
```

`record_seq` ran 1..299 with exactly 2 pages per record, contiguous, zero gaps,
on 598 of 598 pages. It is a layout-independent record delimiter that does not
depend on parsing any student field.

### The two pages carry disjoint identifiers

| Field                             | Page 1  |     Page 2     |
| --------------------------------- | :-----: | :------------: |
| Student name                      |  full   | initial + last |
| Family Portal access code (6 hex) | 299/299 |       --       |
| State student ID (10 digit)       |   --    |    299/299     |
| Date of birth, grade, school code |   --    |    299/299     |

A per-page state-ID extractor finds an ID on exactly half the pages and orphans
every page 1 unless it infers that the preceding page belongs to the following
ID. That inference is the likely root of the prior pagination bugs, and it is
why this design segments on `record_seq` rather than on the student ID.

### Parse quality and reconciliation

- Text layer extracts natively. No OCR required.
- 299 distinct state IDs in 299 occurrences: exact 1:1, no duplicates, and zero
  8- or 9-digit near-misses to disambiguate.
- PDF records reconciled against the state manifest: 299 matched, 0 in manifest
  without a PDF, 0 in PDF without a manifest row.

### The manifest has no campus field

`Accountable School Code` was `7325_965` on all 598 rows. The state provides
nothing below the LEA. **Campus assignment is entirely a PowerSchool join**,
which makes the frozen roster snapshot the sole source of campus truth rather
than one option among several.

`Testing School Code` differed from `Accountable School Code` on 2 rows, so both
fields are retained.

### Identifier chain

The PDF and the manifest carry **different** identifiers, so this is two joins,
not one. The PDF never joins to PowerSchool directly -- the manifest is the
bridge.

| Step | From           | To          | Key                                                                  |
| ---- | -------------- | ----------- | -------------------------------------------------------------------- |
| 1    | ISR PDF record | manifest    | **state student ID** -- the only identifier the PDF carries (page 2) |
| 2    | manifest       | PowerSchool | `Local Student Identifier` or `State Student Identifier`             |

Step 1 is settled: a 10-digit state ID, 299 distinct in 299 occurrences,
reconciling 1:1 against the manifest with zero orphans in either direction.

Step 2 has two candidate keys, and PowerSchool exposes a column for each:

| Manifest column            | PowerSchool column                                                 | Manifest population |
| -------------------------- | ------------------------------------------------------------------ | ------------------- |
| `Local Student Identifier` | `student_number` (projected as `pearson_local_student_identifier`) | 295 / 299           |
| `State Student Identifier` | `state_studentnumber`                                              | 299 / 299           |

`base_powerschool__student_enrollments` already projects
`student_number as pearson_local_student_identifier`, documented as the KIPP
`student_number` reported by the vendor for all NJ regions. Cambium kept
Pearson's field semantics, which is why that column still applies.

Zero conflicting values and zero collisions across students on either key.

**Open: which key leads.** The state ID has better manifest population (299 vs
295), but `student_number` is PowerSchool's own primary key whereas
`state_studentnumber` can be absent for students not yet submitted to the state.
Only the manifest side was measured; neither join was tested against
PowerSchool. The plan must measure both match rates and order the tiers on
evidence. A student matching on neither key is `Unsorted` with reason
`no_sis_match`.

### Grain and status

- Manifest grain is **student x subject** (ELA and Mathematics, 2 rows per
  student).
- PDF grain is **student** (one record covering both subjects).
- `Test Status` carries real variance: 5 `pending` and 1 `invalidated` in
  Newark. Those students still have a PDF, with `NOT TESTED` pages.

### Sensitivity

The manifest is 225 columns including gender, seven race/ethnicity columns,
primary disability type, special education placement, IEP fields, multilingual
learner status, migrant status, homelessness, and economic disadvantage status.
It is considerably more sensitive than the score report it describes. Nothing
campus-facing in this design projects those columns.

## Decisions

| #   | Decision                                                                                                  |
| --- | --------------------------------------------------------------------------------------------------------- |
| 1   | One packet PDF per campus per grade                                                                       |
| 2   | Packets are frozen once and never regenerated; a live Google Sheet is the pointer                         |
| 3   | The Sheet links to the campus-grade packet plus a page-number column. No per-student PDFs, no web service |
| 4   | Region-wide read access on all packets within a region                                                    |
| 5   | Digital only. State paper is out of scope; campuses print the packets                                     |
| 6   | One `Unsorted` packet per region, referenced from the Sheet like any campus                               |
| 7   | Distribution evidence is out of scope                                                                     |
| 8   | Two frozen tables and one live projection                                                                 |
| 9   | The parse aborts rather than guesses; reconciliation gates the renderer                                   |
| 10  | NJGPA first, NJSLA second. The design is assessment-agnostic; the rollout is not                          |
| 11  | The Sheet lists every currently-enrolled student in the assessed grades, blank where no report exists     |

### Rationale for the two that are least obvious

**Region-wide packet read (4).** A student who transfers between campuses after
the freeze has their report inside the _former_ campus's packet. Under
per-campus access the receiving campus cannot open it, which reproduces the
exact failure this project exists to fix. Region-wide read is defensible on the
coterminous-LEA fact and removes every human step and broken link. The accepted
cost: any campus ops user can open any packet in their region and therefore see
those students' Family Portal access codes.

**`Unsorted` as a packet rather than a queue (6).** Making the Sheet the single
lookup surface means `Unsorted` is not a place someone must remember to check;
it is a value in the column they were already reading. This solves findability.
It does **not** solve the mandate -- nobody is tasked with shrinking the
unsorted count -- so the per-region unsorted count is surfaced on the Sheet for
visibility. Acting on it is an ops decision outside this system.

## Architecture

Six components. One is new; the rest extend patterns already in the repo.

### Library change: PDF extraction

`teamster/libraries/sftp/assets.py` already supports PDF sources via a
`pdf_row_pattern` parameter, used today by `kippmiami/fldoe`. Its
`extract_pdf_to_dict` runs one regex per page and returns `m.groupdict()`.

The ISR needs two things it does not provide:

- **page position**, to compute page ranges
- **per-field patterns**, because the state ID is on page 2 and the access code
  on page 1, so a single regex spanning both would be fragile

Both changes are additive: emit `page_number` on each record, and accept a
mapping of named field patterns alongside the existing single-pattern form so
the current `kippmiami/fldoe` caller is unaffected.

### Ingestion asset plus sensor registration

A `build_sftp_file_asset` per region for the ISR PDF, anchored on the footer
token so that every page yields a record. Lands Avro to GCS and is exposed to
dbt as an external source, exactly like the existing manifest CSV assets.

The asset must also be added to each region's `build_couchdrop_sftp_sensor`
`asset_selection`, in `code_locations/kippnewark/couchdrop/sensors.py` and the
Camden equivalent. Without that registration the asset never fires on file
arrival.

The sensor derives partition dimension values from named groups in the file
path, so `remote_file_regex` must carry them. For the observed filename shape:

```text
(?P<fiscal_year>\d{4})_(?P<administration>[A-Za-z]+)_(?P<district>\d{4})-(?P<school>\d+)_ISR_(?P<assessment>\w+)\.pdf
```

This is a new pattern rather than a reused one, and it is the piece most likely
to need adjusting when the first NJSLA files land under filenames not yet
observed.

### dbt models

| Model                           | Grain                | Purpose                                                                             | Frozen  |
| ------------------------------- | -------------------- | ----------------------------------------------------------------------------------- | :-----: |
| `stg_*__isr_pages`              | page                 | one row per page: `record_seq`, `page_number`, plus whichever fields matched        |   no    |
| `int_*__isr_records`            | student x assessment | group by `record_seq` to `page_start`/`page_end`; coalesce state ID and access code |   no    |
| `int_*__isr_roster_snapshot`    | student              | enrollment captured at the freeze instant; campus and grade                         | **yes** |
| `rpt_*__isr_packet_assignments` | student x assessment | campus or `Unsorted`, deterministic order, packet-relative page numbers             | **yes** |
| `rpt_gsheets__nj_isr_index`     | student x assessment | the Sheet projection                                                                |   no    |

### Packet renderer

A Dagster asset that reads `rpt_*__isr_packet_assignments`, slices the source
PDF per `(campus, grade_level)` in the frozen order, and writes each packet plus
the per-region `Unsorted` packet to Drive via the existing
`GoogleDriveResource`.

Couchdrop mirrors the source PDF into Drive already, so the renderer reads from
Drive and writes back to Drive with no GCS round trip.

Runs once per administration, manually triggered. For the first administration
the data team lead (@anthonygwalters) pulls the freeze and the render; this
should move to a named ops owner once the process is proven.

Packets are written to a new folder beneath the existing school directory in
Drive. That structure is already partitioned by region, so cross-LEA isolation
comes from the existing arrangement rather than from anything this project
builds.

### The Sheet

Delivered through the established `rpt_gsheets__*` model plus
`exposures/google-sheets.yml` pattern. One Sheet per region covering all
assessments, with an assessment column.

The Sheet is a **full outer join** between live enrollment and the frozen
assignment, not a projection of the assignment. That yields three row types:

| Row type                             | Report columns              | Status                                             |
| ------------------------------------ | --------------------------- | -------------------------------------------------- |
| Enrolled, report exists              | packet link, page start/end | at freeze campus, or moved to campus X             |
| **Enrolled, no report**              | **blank**                   | `no report received`                               |
| Report exists, no current enrollment | packet link, page start/end | left the network; report in its freeze-time packet |

The middle row type carries more weight than it looks. Without it, a searcher
who finds nothing cannot distinguish "this student has no report" from "I
searched wrong." A blank row is a definitive answer; an absent row is an
ambiguous one.

The enrollment side is scoped to the grades the assessment actually covers,
derived from the distinct `Grade Level When Assessed` values in the manifest
rather than hardcoded -- otherwise every K-12 student would appear with a blank
row. NJGPA is grade 11 only; NJSLA spans grades 3-9 and varies by subject.

## Data flow

```text
1  ISR PDF lands in Couchdrop        -> mirrored to Drive automatically
2  Couchdrop sensor fires            -> SFTP asset fetches and parses
                                        -> stg_*__isr_pages          (page grain)
3  int_*__isr_records                -> student grain, page ranges resolved
   ---------------------------------------------------------------------------
4  MANUAL: pull the freeze              int_*__isr_roster_snapshot   FROZEN
   ---------------------------------------------------------------------------
5  rpt_*__isr_packet_assignments     -> campus, order, page numbers  FROZEN
6  renderer asset                    -> packet PDFs -> Drive
7  rpt_gsheets__nj_isr_index         -> frozen assignment JOIN live enrollment
8  Sheet refreshes on the normal gsheets schedule, indefinitely
```

Steps 1-3 are automatic on file arrival. Step 4 is the only human decision,
because the 30-day clock starts at receipt and receipt is not schedulable. Steps
5-6 follow from it. Step 7 runs indefinitely thereafter.

## Freeze mechanics

### Two frozen tables, one live projection

Freezing only the roster snapshot is insufficient. If the Sheet recomputes
packet page numbers, any drift in the underlying data shifts them away from the
PDF that was actually rendered, and the Sheet begins confidently pointing at the
wrong page.

`rpt_*__isr_packet_assignments` is therefore also frozen. It is not a
derivation; it is a record of what was rendered.

| Column group                                  | Source                       | Changes |
| --------------------------------------------- | ---------------------------- | ------- |
| Packet link, page start/end, campus at freeze | frozen assignment            | never   |
| Currently enrolled campus                     | live enrollment              | daily   |
| Status                                        | derived by comparing the two | daily   |

Nothing about the artifact moves. Only the "where is this student now" column
changes.

### The snapshot must be captured, not queried

Querying PowerSchool for "enrollment as of the freeze date" **does not work and
is the bug being fixed**. A no-show rollback rewrites enrollment history in
place, so an as-of query returns a different answer next week than it does
today. History here is mutable.

The snapshot must be captured once and never recomputed. An incremental model
guarded on the administration satisfies this:

```sql
{{ config(materialized="incremental") }}

select
    '{{ var("isr_admin") }}' as admin,
    student_number,
    state_studentnumber,
    campus,
    grade_level,
    last_name,
    first_name,
    current_timestamp() as frozen_at,
    '{{ var("isr_receipt_date") }}' as receipt_date
from {{ ref("base_powerschool__student_enrollments") }}
where 1 = 1  -- region and active-enrollment predicates elided for brevity
{% if is_incremental() %}
    and '{{ var("isr_admin") }}' not in (select distinct admin from {{ this }})
{% endif %}
```

Re-running is a no-op for an administration already captured. `receipt_date` is
carried as provenance -- the date the vendor files arrived -- which is worth
recording regardless of how the distribution deadline is ultimately defined.

Whether a guarded incremental or a dbt snapshot is the cleaner mechanism is an
implementation choice for the plan. The **requirement** is that recomputation
cannot change a captured roster.

### Packet-relative page numbers

The Sheet must cite the page number within the file the campus opens, not within
the source PDF:

```sql
sum(page_count) over (
    partition by campus, grade_level
    order by last_name, first_name, state_studentnumber
    rows between unbounded preceding and 1 preceding
)
+ 1 as packet_page_start
```

The sort key comes from the frozen snapshot, not live SIS names. A name
correction against live data would reshuffle the packet and invalidate every
page number already published.

### Campus assignment and `Unsorted` reasons

Two distinct reasons, both landing in the region's `Unsorted` packet with the
reason shown in the Sheet status column:

- `no_sis_match` -- neither identifier resolves to a student
- `no_enrollment_at_freeze` -- the student resolves but was not enrolled
  anywhere in the region at the freeze instant

## Failure handling

### The controlling rule

The renderer does not run unless reconciliation passes. A mis-attributed page
sends one student's report home to another student's family, which is a
disclosure; a blocked render is a phone call. The parse therefore aborts rather
than guesses on any of:

- a page yielding no `record_seq`
- a record whose page count is unexpected for that assessment
- more than one distinct state ID within a `record_seq` group
- a non-zero count on either side of the manifest-to-records full outer join

Implemented as a Dagster asset check on `int_*__isr_records` gating the
renderer.

### Other modes

| Failure                                       | Handling                                                                                                                                                                                  |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Variable pages per record (NJSLA will be 2-4) | Free. `record_seq` segmentation never assumed a page count                                                                                                                                |
| Source file spans multiple grades             | Free. Grade comes from the frozen roster, not the file                                                                                                                                    |
| One region's file arrives before another's    | Partition by district code; regions are independent                                                                                                                                       |
| Re-render after a bug                         | Frozen assignment gives byte-identical output; safe to re-run                                                                                                                             |
| Re-freeze needed                              | Requires deleting that administration's snapshot rows. Documented manual operation, never automatic -- an accidental re-freeze silently invalidates every page number already distributed |
| Access codes visible region-wide              | Accepted consequence of decision 4, recorded rather than mitigated                                                                                                                        |

### Reconciliation grain

Reconciliation compares PDF record to manifest **student**, never to manifest
row. Comparing at subtest grain would flag roughly six phantom missing reports
per administration from `pending` and `invalidated` statuses, training people to
ignore the check.

## Testing

dbt data tests:

- `unique` on `(admin, assessment, state_student_id)` in `int_*__isr_records`
- every manifest student appears in exactly one packet, `Unsorted` included
- page ranges contiguous and non-overlapping within each packet
- `accepted_values` on the status and `Unsorted` reason columns

dbt unit test on the packet-page window function. This is the one place where an
off-by-one produces internally consistent and uniformly wrong output that no
data test would catch. Hand-built four-student fixture.

Python test on the parse, **with a synthesized fixture**. A real ISR PDF cannot
be committed as a test fixture -- every one contains live names, state IDs,
dates of birth and portal credentials. The fixture must be generated: a few
synthetic two-page records carrying the same footer structure.

## Scope

### In

The page-range index, the frozen roster snapshot, the campus binding, the
campus-grade packets, the `Unsorted` packet, the Sheet index, and the
reconciliation gate.

### Out

- **Manifest CSV ingestion.** A separate PR lands the District Summative Record
  File CSVs. This work reads the landed manifest table for the student universe,
  the join keys, and `Test Status`. Nothing else crosses that seam.
- Physical paper sorting and pick lists.
- Per-student PDF artifacts.
- An on-demand rendering service. The page-range index is identical either way,
  so a service remains a pure later addition if retrieval volume or audit
  requirements justify it.
- Distribution evidence tracking.
- Notification or delta-packet machinery.

## Rollout

1. NJGPA first: 425 students across Newark (299) and Camden (126), files already
   in hand, grade 11 only. Low stakes and a complete rehearsal.
1. NJSLA second: grades 3-9, roughly twenty times the volume, more subjects,
   more files, filenames not yet observed.

## Open items

- **Which manifest identifier leads the PowerSchool join.** See _Identifier
  chain_. Both candidate keys need their match rate measured against PowerSchool
  before the tier order is fixed; only the manifest side has been measured so
  far.
- **Whether the existing school-directory permissions grant read across campuses
  within a region.** Decision 4 requires that they do. The existing Drive
  structure guarantees isolation _between_ LEAs, which is the stated guardrail,
  but if school directories are themselves access boundaries then a transferring
  student's receiving campus cannot open the packet holding their report -- the
  exact failure this project exists to fix. If so, packets need a region-level
  location or an explicit per-region reader group instead.
