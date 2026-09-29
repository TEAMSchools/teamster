# SRE's target workbook

How to read SRE's workbook, what each tab holds, and which goals it states. The
reconciliation procedure that uses this is in [goals-sheet.md](goals-sheet.md).

## Sanity-checking the scaffold against SRE's target sheet

SRE maintains the workbook the goals ultimately come from, and its cover sheet
lists the schools they expect to recruit for. That makes it the outside check on
`int_tableau__fresh_enrollment_scaffold` — if a school SRE is recruiting for is
missing from the scaffold, or the scaffold carries one SRE doesn't recognize,
the spine is wrong.

**Workbook:** SRE issues a new one each cycle, so ask the user for its URL; do
not trust an id from memory or from this file. The AY2026 workbook was
`26-27 KNJMIA Application Target Formulas`, id
`1YP8MR--r__7DpS-Al8C9fv0NLAuJI6S6IpW5mObZwdI`. Do not record a new id here. The
school list is on the `cover sheet` tab; per-school grade detail is on
per-region tabs (`KCNA`, `Newark`, …).

**How to read it: the Sheets API as ADC.** The AY2026 workbook was shared with
`codespaces@teamster-332318.iam.gserviceaccount.com`. This is the only path that
yields tab names and real cell addresses, so it is the path to use:

```bash
uv run --with google-api-python-client python <<'PY'
import google.auth
from googleapiclient.discovery import build
creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
svc = build("sheets", "v4", credentials=creds)
# tab names: svc.spreadsheets().get(spreadsheetId=ID, fields="sheets.properties")
r = svc.spreadsheets().values().batchGet(
    spreadsheetId=ID, ranges=["'Newark'!A1:R66"],
    valueRenderOption="UNFORMATTED_VALUE").execute()
PY
```

`UNFORMATTED_VALUE` is required — it returns the unrounded formula output the
rounding rules below depend on. If a 403 appears, the new workbook is not shared
with the service account: ask SRE to share it rather than falling back to a
lossy path.

**Do not use the Drive connector to read VALUES.** It runs as the signed-in
user, so access is not the issue — structure is. `read_file_content` has no
tab/range parameter and concatenates every tab into one unattributable blob;
`download_file_content` as CSV returns the FIRST TAB ONLY; as xlsx/zip it
returns base64, and decoding needs a base64-to-shell pipe that
`check-sensitive.sh` blocks. Use the connector for exactly one thing —
`get_file_metadata` for `modifiedTime`, `title` and `owner`, the provenance
facts the cell values don't carry. Not screenshots either: a region tab holds
100+ numbers and transcription is error-prone.

**Two things will trip up a naive comparison:**

- **Paterson is absent from the `cover sheet` but DOES have its own tab**
  (per-grade FDOS Target / Budget Target / Seat Capacity / Offer Target for KIPP
  Paterson ES and MS, verified AY2026). So "the workbook is KNJMIA" holds only
  for the cover sheet. Scope Paterson out of a **cover-sheet** count check, or
  its two schools (PPES, PPMS) read as spurious extras — but do not conclude
  from the cover sheet that SRE has no Paterson targets. Ask whether Paterson is
  in scope; in Aug 2026 the answer was no.
- **Abbreviations don't match and the sheet has no `schoolid`,** so this is a
  region + level + count check or a hand-mapped name comparison, never a join:

  | sheet | scaffold   |
  | ----- | ---------- |
  | KRA   | Royalty    |
  | KCA   | Courage    |
  | KMT   | Miami Tech |
  | KLE   | Legacy ES  |
  | KLM   | Legacy MS  |
  | NLHS  | NLH        |

As of AY2026 this check passes: 22 schools expected across the three regions, 22
produced (Newark 12, Camden 5, Miami 5), plus Paterson's 2 outside the
workbook's scope.

**Corroboration worth knowing:** the per-region tabs band Sumner's own rows as
`MS,Sumner Academy,5` and `MS,Sumner Academy,6` while the cover sheet files
Sumner under Camden **ES**. SRE themselves treat grades 5-6 as MS at the grade
level and the school as ES at the school level — which is exactly the per-grade
banding the scaffold's `school_level` reproduces. Don't "fix" that split.

### Tab-by-tab map of SRE's workbook

The workbook has 7 tabs (AY2026): `cover sheet`, `KCNA`, `Newark`, `Miami`,
`KPAT`, `attrition`, `enrollment snapshot offer management`. Read the doc's
_Which goals exist at which granularity_ first, so you know which goals a tab
could possibly source.

**Numbers quoted anywhere in these tab maps are AY2026 verification evidence,
not current values.** They are here to make a structural claim checkable
("column F holds the seat target, and here is how we knew"), never as a lookup.
Read current values from the workbook and the staging table. Column letters,
cell ranges and row numbers ARE durable — those are the layout, and SRE reuses
it across cycles.

**The governing rule, per SRE: only the MAIN table on each tab is a source.
Everything else on the tab is noise.** Every tab holds several secondary tables
— region-grain rollups, column-total rows, side trackers, loose cells — and they
are all out of scope regardless of how convincing they look. Do not spend a pass
deciding whether one might be authoritative; it isn't.

Two reasons this rule is easy to talk yourself out of, both hit in practice:

- **A secondary table can reproduce the right answer exactly.** Newark's lower
  block is headed `Re-Enroll Projection` and `New Students` at region grain and
  matches `round(SUM of unrounded)` of the main table in 24 of 24 cases. It is
  still noise. Agreement is not authority.
- **Secondary tables overlap the main one horizontally**, so parsing a whole tab
  with one column map silently reads the wrong columns — see the
  pinned-row-range section below for the 14 fabricated diffs this produced on
  `Miami`.

**Always cite a column by its full header text plus its letter**, never a
shortened form. The workbook reuses near-identical names across blocks:
`Projected Returners` (main table, Newark col `O`) is not `Returners` (lower
block, col `L`), and `New Students Needed` (main, col `P`) is not `New Students`
(lower block, col `J`). Shorthand invites reading the wrong column.

#### `cover sheet` — fully mapped

Four blocks, only two of which are loadable:

| block           | range     | feeds                                   |
| --------------- | --------- | --------------------------------------- |
| school targets  | `A2:I24`  | `School` granularity, 6 goal_names      |
| region totals   | `K2:N5`   | **nothing** — Tableau computes these    |
| App Target grid | `A26:D37` | `Region/Grade Level`, `App Target` only |
| grid total row  | `A38:D38` | **nothing** — a `Total`, not a grade    |

School-targets columns: `A` region, `B` type (→ `school_level`), `C` school, `D`
FDOS Target, `E` Seat Target, `F` Budget Target, `G` Re-Enroll Projection, `H`
New Student Target, `I` App Target. 22 schools (Newark 12, Camden 5, Miami 5);
Paterson is on `KPAT`, not here.

Note row 1 is BLANK — the header is row **2**, data rows 3-24. A range starting
at `A1` shifts every row index by one.

Four traps in this tab:

- **The two "totals" blocks (`K2:N5` and row 38) have no home in the staging
  table** — there is no grade-less region granularity. They are labelled and
  numeric and look loadable; they are not. Use them as cross-checks only.
- **`KMT` / `KLE` / `KLM` have col `F` populated with col `E` blank.** Col `F`
  is `Budget Target`, as its header says, for these three as for every other
  school; load it that way. Their `Seat Target` comes independently from the
  `Miami` tab's col `H` per-grade sums, and for a school that opens at capacity
  the two land on the same number (AY2026: 90 / 196 / 56 for both goals, checked
  2026-09-09). So equal values are not evidence the columns were conflated:
  check that BOTH goals are populated before reporting a regression, and do not
  "restore" a NULL. Col `F` is a distinct measure because it differs from col
  `E` for many schools that carry both (9 of 19 in AY2026). Re-derive any
  single-cell example from the current workbook before quoting it, and never
  report a cell as changed just because it no longer matches a number written
  here.

- **The App Target grid stops at grade 10** (rows 27-37 = K,1..10). HS grades 11
  and 12 have no grid row at all, so `Region/Grade Level` `App Target` is NULL
  for them even where a school carries one. Verified AY2026: Camden KHS has
  `School/Grade Level` App Target 19 at grade 11 and 0 at grade 12, while the
  Camden region rows for both grades are NULL — so the region figure understates
  Camden by 19 applications. Newark's grades 11-12 are NULL on both sides
  (NCA/NLH carry no App Target there), so the gap is Camden-only and is a
  question for SRE, not a derivation bug.
- **The grid's Miami grades 9 and 10 hold a literal `0`** while prod holds NULL.
  Correct — MTH is a matriculation school with no application funnel (below),
  and no Miami school recruits at grade 10. Do not "fix" NULL to 0.

**The grid is meant to equal the per-grade sums, so use that as a check.**
Verified AY2026: the grid matched `SUM` of the region tab's own per-grade col
`R`/`S` rows on **32 of 34** comparable cells. The two that did not are Camden
grade 5 (grid 69 vs Sumner r14 32 + LSM r17 21 + Hatch r22 48 = **101**) and
grade 6 (grid 71 vs 47 + 42 + 29 = **118**). Prod follows the grid. Given the
other 32 cells agree exactly, those two grid cells look stale rather than
authoritative — but both are main-table sources, so this goes to SRE as a
question rather than being resolved here.

#### `KCNA` — fully mapped

**Only block 1 (rows 3-31, header row 2) is a source.** It carries two
granularities at once:

| granularity          | rows                               | goals                                                            |
| -------------------- | ---------------------------------- | ---------------------------------------------------------------- |
| `School/Grade Level` | the per-grade rows                 | Seat `J`, FDOS `L`, Re-Enroll `O`, New Student `P`, App `R`      |
| `School`             | the 5 `Total` rows (8,16,21,26,31) | same five — **no `Budget Target`**, which stays cover-sheet-only |

Full column read: `A` attrition-by-formula (ignore), `B` type, `C` school, `D`
grade, `E` sections, `F` **SY25-26** seat target (prior year — not a goal), `G`
10.15 enrollment (actual), `H` over/under, `I` backfill, **`J` SY26-27 seat
target**, `K` no-show %, **`L` FDOS Target**, `M` yearlong attrition, `N`
historic retention, **`O` Projected Returners**, **`P` New Students Needed**,
`Q` conversion rate (a calc input, NOT the `Conversion` goals), **`R` # of apps
needed**.

Confirmed not sources, per SRE: **columns `S`/`T`**, **row 32** (an unlabeled
region summary), and **the entire table from row 33 down** (the `City` /
`Campus` / `Grade Level` block). That last one is a trap worth knowing:

- It looks authoritative — it has a `New Students Needed` and an `App Goal`
  column at school × grade grain, and an unlabeled column `K` that is a perfect
  per-grade sum of its campuses. None of it is a source.
- It uses **different school abbreviations** (`KSE` for Sumner, `KHM` for Hatch
  Middle) that appear nowhere else in the workbook, so a school-name map will
  silently match `KHS` from its `Campus` column and read the wrong columns.
- Its column `K` (99 at Camden grade 5) lands near the main table's per-grade
  sum (101), which can make it look like a tiebreaker against the cover-sheet
  grid (69). It is not. The real disagreement is between two sources, the grid
  and the main table's rows; see the `cover sheet` section.

The `School` totals overlap the cover sheet on all five goals, so they are a
free cross-check rather than a competing source. Note Sumner's rows split `ES`
(K-4) and `MS` (5-6) in the `Type` column while its `Total` row reads `ES` — the
documented per-grade banding divergence, not an error.

#### `Newark` — fully mapped

Main table is **rows 2-66, header row 1**, and it is the only source on the tab.
Identical column layout to `KCNA`, so the same map applies:

| col | header (verbatim)          | maps to                |
| --- | -------------------------- | ---------------------- |
| `J` | `SY 26-27 Seat Target`     | `Seat Target`          |
| `L` | `FDOS Target`              | `FDOS Target`          |
| `O` | `Projected Returners`      | `Re-Enroll Projection` |
| `P` | `New Students Needed`      | `New Student Target`   |
| `R` | `# of applications needed` | `App Target`           |

Per-grade rows → `School/Grade Level`; the `Total` rows → `School`. As on
`KCNA`, no `Budget Target` column — that stays cover-sheet-only.

Noise on this tab: **row 67** (column totals), **the entire block from row 68
down** (the region-grain rollup, plus its own `Total` at r82), and the loose
cells at r84 and r89-93.

#### `Miami` — fully mapped

**The main table is TWO segments**, both valid, with identical column layouts —
rows **2-13** (header r1: Royalty K-5, Courage 6-8, Miami Tech 9) and rows
**19-29** (header r18: Legacy ES K-5, Legacy MS 6-8). Legacy sits in its own
segment because it is a new school, not because it is secondary.

| col | header (verbatim)       | maps to                |
| --- | ----------------------- | ---------------------- |
| `H` | `26-27`                 | `Seat Target`          |
| `K` | `FDOS Target`           | `FDOS Target`          |
| `N` | `Projected Returners`   | `Re-Enroll Projection` |
| `O` | `New Students Needed`   | `New Student Target`   |
| `R` | `Number of Apps Needed` | `App Target`           |

Segment 2 also has `P` `Total Apps`, which is **not** a goal — ignore it. Column
letters are otherwise identical across both segments, so one map serves both.

Three traps:

- **Two different `Total` rows are both labelled `KRA`.** Row 8 is Royalty's
  total; **row 25 is Legacy ES's** (its `H=196, K=229, N=25, O=171, R=461` match
  prod's Legacy ES `School` row exactly). Row 29's total has **no school name at
  all**. Keying `School` granularity off these rows would write Legacy ES's
  numbers onto Royalty — so take Miami's `School` values from the **cover
  sheet**, which has clean `KRA` / `KCA` / `KMT` / `KLE` / `KLM` rows.
- **Exclude rows 27-28.** Legacy MS grades 7-8 carry no real goal values (r28
  has a stray `0.9` in the seat column, which rounds to a phantom
  `Seat Target = 1`) and prod has no rows for either grade.
- **Noise:** r14-16, r30-31, r33, the r34-46 block (full of `#REF!`), the r51-66
  side table plus its overlapping Legacy / North Campus trackers, r68, r72-83,
  r89-102, r110.

#### Miami Tech is a matriculation school

`MTH` opened for **KIPP's own 8th graders moving up to grade 9**, not for
external recruitment. Everything that looks broken about its goals is therefore
correct:

- **`Projected Returners` = 90 is right.** Those students persist in the network
  even though the school is new — `Re-Enroll Projection` measures persistence,
  not same-school retention. Do not "fix" this by moving the 90 into
  `New Student Target`.
- **`New Student Target`, `App Target` and `Offers Target` are legitimately
  NULL**, and the tab's `Conversion Rate` / `Number of Apps Needed` columns are
  legitimately empty. There is no lottery and no application funnel.
- This is **why** MTH lacks the `Accepted` / `Offers` / `Pending Offers`
  categories at `School` granularity. It is not an unexplained quirk.

The one real consequence: `Region/Grade Level` `Re-Enroll Projection` for Miami
grade 9 should pick up MTH's returners (AY2026 prod held NULL there), while
grade 9 `New Student Target` correctly stays NULL because there is nothing to
sum.

#### `KPAT` — fully mapped

Paterson. Main table is **rows 2-12, header row 1** — everything from r14 down
is noise, including another pair of horizontally-overlapping tables at r20-31.

**A third distinct column layout** — not the NJ tabs' `J/L/O/P/R`, not Miami's
`H/K/N/O/R`:

| col | header (verbatim)       | maps to                              |
| --- | ----------------------- | ------------------------------------ |
| `A` | `Type`                  | `school_level` — **and the row key** |
| `B` | `School`                | `school`                             |
| `C` | `Grade`                 | `grade_level`                        |
| `G` | `Seat Capacity`         | `Seat Target` (non-standard header)  |
| `H` | `Budget Target`         | `Budget Target` — **School only**    |
| `M` | `FDOS Target`           | `FDOS Target`                        |
| `P` | `Projected Returners`   | `Re-Enroll Projection`               |
| `Q` | `New Students Needed`   | `New Student Target`                 |
| `S` | `Number of Apps Needed` | `App Target`                         |

`D`/`E`/`F` are prior-year actuals, `I`/`N`/`O` and `R` are calculation inputs,
`U` is sections. **`W` `Offer Target` is ignored per SRE** — it is the only such
column in the workbook, and using it would make Paterson the only region with a
reconcilable `Offers Target`.

Rows: Paterson ES K-4 then its `Total`; Paterson MS 5-8 then its `Total`.

Three Paterson-specific rules:

- **Both `Total` rows are labelled `KPES`.** Key `School` granularity off column
  `A` (`ES` → PPES, `MS` → PPMS), never the school name — the same trap as
  Miami's two `KRA` totals.
- **`H` `Budget Target` is per-grade here, but stg models `Budget Target` at
  `School` only. Do not add a granularity for it** — load only the `Total` row
  value. (The per-grade values sum to the `Total`, so either reading agrees;
  take the stated `Total`.) Miami is the opposite case: no `Miami` block carries
  a budget column, so Miami's `Budget Target` comes only from the cover sheet's
  col `F`.
- **Paterson is absent from the cover sheet**, including its `App Target` grid,
  so Paterson's `Region/Grade Level` `App Target` is **derived** where the other
  three regions' is sourced. With one school per grade the "sum" is that
  school's own value.

#### `attrition` and `enrollment snapshot offer management` — noise

Confirmed not goal sources. The five source tabs are `cover sheet`, `KCNA`,
`Newark`, `Miami` and `KPAT`; nothing else in the workbook feeds the goals
sheet.

### Sourced vs derived: check before reconciling

**Match what the workbook states; derive only what it doesn't.** In that order —
never compute a value the workbook already states, even when computing gives a
tidier or more testable answer. See the doc's _Sourced vs derived goals_ for the
current split.

**Search every tab before concluding "derived."** A goal can be stated on one
region's tab and absent from another's, so this is a whole-workbook conclusion,
not a per-tab one. Classifying off a single region is how you end up recomputing
something SRE already told you.

Two operational consequences:

- **Apply `School/Grade Level` edits first, then recompute the region rows.**
  They are a function of the school rows, so the reverse order keys the region
  rows to superseded values.
- **Round a derived aggregate once: `round(SUM of unrounded)`,** never the sum
  of rounded values (the doc's _Sourced vs derived goals_). Prod matches
  `round(SUM)` wherever the two differ, so it needs the tabs' unrounded values,
  and a region row can sit 1 off the sum of the school rows a reader sees. Say
  which method you used.

### Rounding: half-up, and NOT Python's `round()`

SRE's sheets store **unrounded formula output** while the goals sheet holds
integers, so every comparison must round before diffing. Two ways to get this
wrong, both of which manufacture false diffs across dozens of rows:

- **Not ceiling.** Verified against AY2026 prod: SPARK `415.17` → 415, Seek
  `405.11` → 405, Rise `398.248235318` → 398, NCA `774.44107857` → 774, Life
  `220.34` → 220, KURA `194.31` → 194, TEAM `50.08` → 50. Ceiling would have
  been wrong on every one.
- **Not `round()`.** Python's built-in is banker's rounding, so
  `round(390.5) == 390` while the sheet and prod both hold **391** (THRIVE's
  Re-Enroll Projection). Use explicit half-up:

  ```python
  from decimal import Decimal, ROUND_HALF_UP

  def half_up(x):
      return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
  ```

Which columns need it varies by tab — on the `cover sheet` only `G` and `H` are
fractional; `D`, `E`, `F`, `I` are clean integers. Don't assume; check.

### Read the tabs with the Sheets API, and pin row ranges

`values.get` with `range="'Newark'!A1:AZ200"` and
`valueRenderOption="UNFORMATTED_VALUE"` gives real cell addresses, which is what
makes a discrepancy claim attributable. **But every region tab has second and
third tables further down whose columns overlap the first**, so parsing a whole
tab with one column map fabricates diffs. This actually happened: parsing the
`Miami` tab unbounded produced 14 invented Legacy discrepancies (a "Seat Target
28 → 446") by reading a North Campus progress tracker's `Application Target`
column at rows 51-58. Pin explicit row ranges per block, and sanity-check any
implausible magnitude before reporting it.

**Pull the goals table with the BigQuery Python client on ADC** (client choice:
`.claude/context/claude_ai_Google_Cloud_BigQuery.md`). A full comparison needs
every sheet-sourced row at once (~700 for the six SRE targets, ~2,300 for the
whole tab). For a spot check, one `string_agg` per
`(goal_granularity, goal_name)` through the MCP returns a dozen rows instead of
hundreds.
