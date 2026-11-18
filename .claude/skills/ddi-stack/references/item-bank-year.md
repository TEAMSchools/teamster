# Item Bank assessment year stuck on last year

For an Illuminate Item Bank assessment that shows this school year in Illuminate
but last school year in the warehouse and the AppSheet app.

## Symptom

- The AppSheet app says an assessment is already tagged, but the assessment is
  missing from the app and its export, or the app's form shows last school year.
- Illuminate's Assessment Settings screen (Item Bank editor, gear icon,
  **General** tab, **TAGS**) shows this year's **Assessment Year**.
- `academic_year` in
  `dagster_kipptaf_dlt_illuminate_dna_assessments.assessments` is last year's.
  Illuminate dates a year by its spring, so 2026-27 is `2027`.

The tag is real. The extension row is keyed by `assessment_id` and survives; the
app files the assessment under `academic_year_clean`, so it disappears when last
year is hidden in the app. Do not re-tag it. Do not tell the requester to set
the year in Illuminate: the screen already shows the right year.

## Cause

Item Bank (`assessment_type = 'ibx'`) settings save outside
`dna_assessments.assessments` and normally write back. A copy of a prior-year
assessment (`duplicate_from_assessment_id`) can keep the source's
`academic_year` after someone sets the new year on the settings screen. The sync
is not the cause: the dlt asset replaces the whole table on every run.
`administered_at` is null on every `ibx` row, so a null there is not a symptom.

## Find every affected assessment

Set the title pattern and the wrong `academic_year` for the year at hand (for
2026-27: titles say `2026 - 2027` or `26-27`, the wrong value is `2026`).

```sql
select
    a.assessment_id,
    a.itembank_assessment_id,
    a.title,
    a.academic_year,
    a.duplicate_from_assessment_id,
    src.academic_year as source_academic_year,
    e.assessment_id is not null as is_tagged,
from `teamster-332318.dagster_kipptaf_dlt_illuminate_dna_assessments.assessments` as a
left join `teamster-332318.dagster_kipptaf_dlt_illuminate_dna_assessments.assessments` as src
    on a.duplicate_from_assessment_id = src.assessment_id
left join `teamster-332318.kipptaf_appsheet.illuminate_assessments_extension` as e
    on a.assessment_id = e.assessment_id
    and e.source = 'illuminate'
where a.deleted_at is null
    and a.assessment_type = 'ibx'
    and regexp_contains(a.title, r'2026\s*-\s*2027|26-27')
    and a.academic_year = 2026
```

Rows with a prior-year `source_academic_year` are the copy case. Rows with no
source are not copies; confirm with the owner that they belong to this year
before re-saving them.

## Fix: re-save the year

In Illuminate, for each assessment:

1. Open the DnA overview page
   (`https://kippteamschools.illuminateed.com/live/?assessment_id=<assessment_id>&page=Assessments_Overview_Controller#/empty`)
   and click **View**, which opens the Item Bank editor. The direct editor link
   is
   `https://kippteamschools.illuminateed.com/live/?itembank_assessment_id=<itembank_assessment_id>&action=itembankAssessment&page=Dna_IBXController`.
2. Click the gear (**Settings**) icon. Set **Assessment Year** to last year (for
   example `2025-2026`). Wait for **✓ Saved** in the header, close the window,
   and click **Done**.
3. Click **View** again. Set **Assessment Year** to this year (for example
   `2026-2027`). Wait for **✓ Saved**, close the window, and click **Done**.

Do both passes, with **Done** after each. A single save of the same value is not
the tested fix. Pick the year from the dropdown list; the small **×** inside the
field clears it.

The procedure covers `ibx` assessments only. A non-Item Bank assessment has no
Item Bank editor.

## Verify

1. Launch `kipptaf/dlt/illuminate/dna_assessments/assessments` once the user
   asks (Dagster+ `launch_asset_run`, deployment `prod`), or wait for the next
   run of `illuminate_dlt_hourly_asset_job_schedule`.
2. Confirm `academic_year` changed in the raw table, then in
   `kipptaf_illuminate.stg_illuminate__dna_assessments__assessments`, a table
   that rebuilds a few minutes after the load. `int_illuminate__assessments`
   through `rpt_appsheet__assessments` are views and follow staging at once.
3. The requester syncs the AppSheet app.

A newer `updated_at` shows the save reached the database even when the year did
not change. Illuminate stores it as local time without a zone, so formatting it
in `America/New_York` reads 4 or 5 hours early.

## Many assessments: a browser agent

Hand a browser agent (Claude in Chrome, the most capable model at medium effort)
the prompt below. Fill the table from the query above. Have the user watch the
first assessment through both passes before the agent continues.

```text
You are updating the Assessment Year on Item Bank assessments in Renaissance DnA (Illuminate) for KIPP Team & Family Schools. I am already logged in at kippteamschools.illuminateed.com in this browser.

## Why

These assessments show Assessment Year "<THIS YEAR>" in their settings, but Illuminate's database still has them as <LAST YEAR>. Re-saving the year fixes it: set it to <LAST YEAR> and click Done, then set it back to <THIS YEAR> and click Done again. Every assessment must end at <THIS YEAR>.

## Assessments to update

Do them one at a time, in this order. Before changing anything, check that the title on the page matches the title below (ignore trailing spaces).

| # | Assessment ID | Item Bank ID | Title |
|---|---|---|---|
<ROWS>

Assessment overview page (start here):
https://kippteamschools.illuminateed.com/live/?assessment_id=<Assessment ID>&page=Assessments_Overview_Controller#/empty

Direct link to the Item Bank editor (use only if the View button does not open the editor):
https://kippteamschools.illuminateed.com/live/?itembank_assessment_id=<Item Bank ID>&action=itembankAssessment&page=Dna_IBXController

## Steps for each assessment

### Pass 1: set the year to <LAST YEAR>

1. Open the overview page for the Assessment ID. The blue header shows the assessment title. Confirm it matches the table.
2. Click the blue "View" button at the top right, next to "Administer". The tab moves to ibx.illuminateed.com. It may show an empty "Browse Items" page for a moment. Wait until the green header shows the assessment title and the items list loads.
3. Click the gear icon in the green header. Its tooltip is "Settings", and it sits between the "?" icon and the download icon. An "Assessment Settings" window opens on the "General" tab.
4. Under "TAGS", read the "Assessment Year" value and record it as the starting value.
   - If it reads "<THIS YEAR>", continue to step 5.
   - If it already reads "<LAST YEAR>", skip to Pass 2, step 3, and record that you did.
   - If it reads anything else or is blank, change nothing. Close the window, record the value, and move to the next assessment.
5. Click the Assessment Year dropdown and pick "<LAST YEAR>" from the list. Pick the option by its exact text. The list also includes options like "Repeat Yearly" and other years. Do not click the small "×" inside the field, because that clears the year.
6. Wait until "✓ Saved" appears in the green header, left of the "?" icon. If it does not appear within about 10 seconds, stop and report.
7. Close the Assessment Settings window with the "×" at its top right corner.
8. Click "Done" at the top right of the green header. Wait until you are back on the DnA overview page (kippteamschools.illuminateed.com, blue header).

### Pass 2: set the year back to <THIS YEAR>

1. On the overview page, click "View" again and wait for the editor to load.
2. Click the gear "Settings" icon. Confirm Assessment Year now reads "<LAST YEAR>". If it does not, stop and report.
3. Click the dropdown and pick "<THIS YEAR>".
4. Wait for "✓ Saved" in the green header.
5. Close the Assessment Settings window with its "×".
6. Click "Done" and wait for the DnA overview page.
7. Record the final value as <THIS YEAR>.

## Do not

- Do not change any other field: Scope, Subject, Grade Levels, First Date Administered, or Lock All Items.
- Do not change the Question Groups tab, Description, the "Tags" button, items, standards, or weights.
- Do not click "Administer", "Create Item", "Create Assessment", the copy/duplicate icon, "Advanced Settings" on the overview page, or anything that deletes.
- Do not touch any assessment not in the table.
- Do not type a password or log in. If Illuminate asks you to sign in, stop and tell me.
- If a pop-up asks you to confirm something you were not told to expect (for example, a warning about student results), click Cancel or close it, change nothing more on that assessment, and report it.

## Stop and report if

- The page title does not match the table.
- "✓ Saved" never appears.
- The Settings window looks different from what is described here.
- Any error message appears.

When you stop on one assessment, finish recording it, then continue with the next one, unless you are signed out or every page is failing.

## When finished

Reply with one row per assessment:

| Assessment ID | Title matched? | Starting year | Pass 1 saved? | Pass 2 saved? | Final year | Notes |

Then list any assessment you skipped or stopped on, and why.
```
