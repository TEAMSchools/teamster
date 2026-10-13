# Schools tab verification -- missing-school case work log

Full work log for `SKILL.md` Step 5 (Verify the Schools tab), covering the Excel
export/import mechanics and a real missing-school case worked end to end.
Referenced from `SKILL.md`; read this before touching the Schools List task's
Excel export/import flow, since the Portal Guide's own wording gets some of this
wrong (see "Import cannot create the new rows" below).

**Working a real missing-school case (2026-2027 cycle: KIPP Legacy Elementary,
KIPP Legacy Middle, KIPP Miami Technical High), what actually worked:**

- **Export mechanics, confirmed live.** Click **Export** on the grid toolbar
  (next to Reload/Freeze/Import/Edit/Update/Reset) -> a dialog offers CSV, Excel
  File, or Formatted Excel File. Pick **Excel File**. Leave both toggles off
  (**"Do not export record Id(s)"** and **"Export only selected records"**) --
  you need the record Ids for reimport to update rather than duplicate, and you
  need every row, not a subset. Rename away from the default `List Export`
  filename, then click Export.
- **`State/Province` displays as the full state name in the live grid**
  (`New Jersey`, `Florida`), not the two-letter abbreviation -- match that in
  any row you add or edit, not `NJ`/`FL`.
- **The working loop with Claude**: export the file, open it, copy the entire
  sheet (header row plus every data row), and paste that as plain text into the
  chat -- pasting straight from Excel without "paste as plain text"
  (`Ctrl+Shift+V`/`Cmd+Shift+V`) often inserts an image instead of usable text.
  Claude appends the new schools' rows and rewrites the header row to the real
  import-mapping field names (see below), leaving every existing row's data
  untouched. Paste that back into the same Excel file (replacing its contents),
  format the NCES ID and ZIP/Postal Code columns as Text first (Excel mangles
  long digit strings and leading zeros otherwise), then Import.
- **Import cannot create the new rows -- confirmed twice.** Per the Portal
  Guide's own Export/Import section: "You cannot add any new rows as the import
  is only to update the records." A real submission attempt using CSGF's own
  "Schools List Mapping" import template proved this isn't just the Guide's
  wording -- it failed all 3 new-school rows with
  `MISSING_ARGUMENT:Id not specified in an update call`. That template's
  underlying operation is update-only regardless of what the Validation screen's
  `Operation` field displays (it showed `Insert` in an earlier, different
  attempt). **Sequence has to be Add Record (creates the bare row with a real
  Id) first, then export the now-larger grid, fill in field values, reimport.**
- **Add Record works, but it's manual, one school at a time, and slow** --
  confirmed live for the 2026-2027 cycle (KIPP Legacy Elementary added this
  way). Click **Add Record** on the grid toolbar, hand-enter values into the new
  blank row's fields (it accepts pasted text per field, not a pasted
  multi-column row), then repeat per school. There's no bulk-create path; budget
  time for this per missing school.
- **In the grid's edit mode, a copied value can be pasted down multiple rows of
  the same column at once** -- select the rows for that column and paste; this
  is real and confirmed, distinct from the field-by-field entry Add Record
  itself requires. Useful for values every new-school row shares
  (`Country/Territory`, `Geographic District`, etc.) once the bare records exist
  and you're filling in the rest of their fields.
- **Schools List doesn't have to fully close before moving on to Step 6.** Once
  the bare records exist, tag Laz asynchronously for the remaining fields and
  proceed -- don't block the whole collection on his availability. Carry the
  open items into Step 6's item-list doc as one of the "open questions" it's
  meant to hold before sharing.
- **Status as of 2026-09-11: all 3 bare records added** (KIPP Legacy Elementary,
  KIPP Legacy Middle, KIPP Miami Technical High) via Add Record. **Still needs
  Laz to review and enter the remaining data** -- specifically the fields this
  session confirmed have NO source anywhere in the codebase (checked
  `int_finance__enrollment_targets` and `int_tableau__fresh_goals_scaffold`,
  both ruled out for seat capacity): `Total Seats at Full Scale`, `School Model`
  (+ Notes), `Facility Ownership Type`, `Lease Term Including Extensions`,
  `Facility Serve Long Term Needs`, `New Lease/Building in 2 Years`,
  `Real Estate Financing in Calendar Year` (+ Amount Financed, Lenders). These
  need direct input from Laz/the schools, not more codebase digging.
- **`int_students__schools` is the source of truth for whether a school exists**
  -- not `int_extracts__student_enrollments`'s year range. A school having no
  enrollment history before the current year does NOT mean it's newly opened;
  Miami's Focus cutover already destroys history for reasons unrelated to when a
  school actually opened. Don't infer "new vs. long-standing" from
  enrollment-extract year ranges -- check `int_students__schools` for existence,
  and check the school's own public page (below) for its actual founding year.
- **State School ID encodes a shared charter number, not a per-school code.**
  Format is `[FL district code]-[charter number]` (e.g. `13-2332`). Focus's own
  `school_number` (`custom_327`, e.g. `2332C`) reveals the grouping: the letter
  suffix is the campus, the number prefix is the charter. KIPP Miami runs (at
  least) two charters -- `2332` (Royalty, Courage, Miami Tech, and the closed
  Liberty) and `2008` (Legacy Elementary, Legacy Middle, and the closed
  Sunrise). Confirmed against CSGF's existing Portal record: Royalty and Courage
  (both charter `2332`) share the exact same `13-2332` code.
- **`stg_google_sheets__people__locations.address`/`postal_code` are null for
  every Miami row**, not just newly-added ones -- confirmed by checking Royalty
  and Courage, which have real known addresses. This is a real gap in that sheet
  for the whole region, not something to keep re-checking per school. **The real
  source is Focus's own raw dlt table**, under custom-field codes, not yet
  staged into any dbt model:
  `dagster_kippmiami_dlt_focus.schools.custom_200000319` (Address) and
  `custom_200000322` (Zipcode). Decode any other missing school attribute the
  same way: `dagster_<district>_dlt_focus.custom_fields` filtered
  `source_class = 'SISSchool'`, matched on `title`.
- **Cross-check against the school's own public page**
  (`kippmiami.org/kipp-<slug>/`) before trusting either internal source alone --
  it independently confirmed both the Focus addresses AND surfaced a real typo
  in CSGF's existing Portal record for Royalty/Courage (`300 NW 110th Street`,
  missing a digit vs. the real `3000 NW 110th Street`). The same pages also
  carry each school's founding year ("20XX FOUNDED" in their key-facts section),
  which answers "did this school open this cycle" -- but that's not the same as
  having a value for the `Academic Year Opened` column itself.
- **`Academic Year Opened`/`Academic Year Closed` are Salesforce lookup IDs, not
  text.** The column holds an opaque record ID (`9TPa5000000FbZvGAK` style).
  There's no way to derive the right ID for a school year that isn't already
  used by an existing row (the sheet only goes up to `2025-2026`), so leave the
  ID column itself blank and pick the year from the Portal's own dropdown --
  don't fill in the literal year text there, that's an invalid value for an ID
  field. The adjacent `* Name` column, despite reading as a calculated display
  value, DOES accept the literal year text directly (`2026-2027`) -- fill that
  one in.
- **Excel silently mangles NCES ID / State School ID / ZIP on paste** if the
  destination column isn't formatted as Text first -- large all-digit strings
  and leading zeros get eaten by Excel's automatic number conversion. Fix is
  formatting the destination cells as Text before pasting, not a leading
  apostrophe in the value itself.
- **Excel does the same thing to date-looking values, and it's a real
  submission-breaking error, not just a cosmetic one.** Confirmed from an actual
  error-report CSV: pasting `2026-07-01` into `Next Charter Renewal Date` and
  `2025-07-01` into `Date of Takeover, Merger, or Turnaround` silently became
  the underlying Excel serial-date integers (`46204`, `45839`) on every row that
  had one, and Salesforce rejected every single one on import with
  `INVALID_FIELD:'<serial>' is not a valid value for the type xsd:date`.
  **Format every date column as Text too, before pasting -- not just NCES
  ID/State School ID/ZIP.** Given this hit every row with a date value, the
  safer instruction for next cycle is to format the ENTIRE destination sheet as
  Text before pasting anything back in, rather than trying to enumerate every
  column that needs it.
- **Confirmed live (2026-2027 cycle): the exported file's own header row does
  NOT work for reimport.** The Portal Guide's "columns must appear in the same
  order with the same headings as when you exported it" describes the export
  step only -- it does not mean those header strings are valid import field
  names. Re-uploading a file with the export's own headers unchanged fails to
  map (no interactive prompt catches this -- it just doesn't work, which reads
  as "Salesforce isn't asking for renames" but actually means the mapping
  silently didn't happen). **The header row has to be replaced with the real
  field names from the import screen's own dropdown before reimporting** --
  expect this every cycle, not just once. Several names genuinely differ from
  the exported header:
  - `Administered NWEA MAP?` -- exported header, but the import dropdown only
    offers **`Did school give NWEA MAP?`**
  - `Administered iReady?` -- import dropdown: **`Did school give iReady?`**
  - `Additional Context` -- import dropdown:
    **`Takeover, Merger, or Turnaround Context`**
  - `Id` -- import dropdown: **`Record ID`** (a separate `AIM School Id` also
    exists -- that's a different, external-system id, not this one)
  - `Submission Status` -- ambiguous: the dropdown offers `Data Status`,
    `School Budget Status`, `School List Submission Status`,
    `School List Verification Submit Status`, and `School Status` as separate
    fields. Untested guess: `School List Submission Status` (name-matches the
    task), but this needs confirming against a row you know the true value for.
- **2026-2027 AP course name list, pasted directly from the Portal task
  (2026-09-11) -- diffed against the pivot's 28 columns.** 3 naming-drift hits,
  all College Board's old "AP Studio Art" naming vs the current names: pivot has
  `AP Studio Art: 2-D Design Portfolio` / `3-D Design Portfolio` /
  `Drawing Portfolio`; CSGF's current list says `AP 2-D Art and Design`,
  `AP 3-D Art and Design`, `AP Drawing`. Harmless as-is (the exported column is
  a snake_case alias a human matches by meaning, not exact string, and none of
  the 3 are currently taught anyway) but fix the crosswalk/pivot naming if any
  school ever offers one. Real missing-column gaps (no pivot column exists at
  all): Chinese/German/Italian/Japanese Language and Culture, Latin, European
  History, Music Theory, Physics 2, Physics C (Electricity and Magnetism /
  Mechanics), AP Research -- none currently taught (confirmed against AY2025
  actual course data), so no live impact this cycle, but any of these
  newly-offered in a future cycle would silently drop per the Coverage risk
  documented in [`known-data-risks.md`](known-data-risks.md). (Calculus BC: AB
  Subscore and the two Music subscores are scoring artifacts, not real course
  offerings -- not gaps.)
  - `Street Address` / `City` / `State/Province` / `ZIP/Postal Code` /
    `Country/Territory` -- each of these has TWO candidates in the dropdown: a
    bare legacy field (`Street Address`, `City`, `State`, `Zip Code`) and a
    compound `School Address (...)` field. **`Country/Territory` only has the
    compound option** (`School Address (Country/Territory)`, no bare equivalent)
    -- since Salesforce compound address fields always group
    Street/City/State/Zip/Country/Lat/Long together as one field, that's good
    evidence the compound `School Address (...)` set is the real, current field
    and the bare ones are legacy/deprecated. Untested; confirm by checking which
    one actually holds a value on an existing row before trusting this for a
    real submission.
  - Every other exported header matched its import-dropdown name exactly (School
    Name, State School ID, NCES ID, Geographic District (+`:District Name`),
    Total Seats at Full Scale, School Model (+ Notes), Takeover/
    Merger/Turnaround?, School Operation Type, Date of Takeover..., Academic
    Year Opened/Closed (+ `:Name` each), Next Charter Renewal Date, Authorizing
    District or Entity, Authorizing Entity Type, Facility Ownership Type, Lease
    Term Including Extensions, Facility Serve Long Term Needs, New
    Lease/Building in 2 Years, Real Estate Financing in Calendar Year, Total
    Amount Financed for Real Estate, Lenders of Real Estate Financing) -- don't
    assume a mismatch on those just because of the ones above.
  - **Before trusting any of this next cycle, re-check the live import mapping
    dropdown yourself** -- Salesforce object fields get renamed/added across
    cycles same as everything else CSGF touches, and this list was captured
    against the 2026-2027 Schools List object specifically.
