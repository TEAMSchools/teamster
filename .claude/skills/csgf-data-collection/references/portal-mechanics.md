# Portal mechanics

Extracted from CSGF's Data Collection Portal User Guide (August 2026).
Referenced from `SKILL.md`. Read the guide itself for anything not covered here.

**The 15 portal tasks** (complete Preliminary Questions, Schools List, and
Growth Plans first -- they inform what other tasks prompt for): Preliminary
Questions, Schools List, Key Contacts, Enrollment, Discipline, School Finance,
Org Finance, Growth Plans, Org Staffing Summary, Org Info Questions, Org Chart
Upload, Budget Upload, Bank Info Verification, Officer Cert, Data Summary.

**Task statuses:** Not Started → In Progress → Ready for Review → Completed, or
Further Edits Needed if CSGF finds an error on review. Not Applicable / Not
Available / Canceled are CSGF-only-settable (if one of these looks wrong on your
task, submit a support ticket rather than trying to change it yourself). Moving
to "Ready for Review" happens automatically in most cases once required
fields/errors are cleared -- **except HSDC tasks**, which you set manually.

**Task types:** Grid (spreadsheet-style, per-field validation), Flow (guided
multi-screen), Survey (fixed questions), or a mix.

**Grid bulk-edit via Excel export/import** (this applies to the main Portal
grids -- NOT the HSDC Google Sheet, see the caution in
[`hsdc-mechanics.md`](hsdc-mechanics.md)):

- Export defaults to Excel format -- keep it that way (don't switch to CSV);
  keep "Do not export record Id(s)" toggled off (default) since you need the IDs
  to re-import.
- Re-import requires: same column order/headers as the export; the `status`
  column left blank or "In Progress" (changing it to "Submitted" in the file can
  break the upload -- use the portal's Submit button instead); no new rows added
  (import only updates existing records -- request new records via a support
  ticket); file must be `.xlsx`, not `.csv`.
- Some fields (e.g. Academic Year Opened/Closed on Schools List) can't be
  mass-updated via import -- expected, not an error.
- Monitor import results via the "GM - Import Monitor" tab (bottom left); errors
  are downloadable as a CSV.

**Reassigning a task to someone else:** the target person needs "Data Collection
Participant = Yes" on the Key Contacts grid **and** an existing portal login, or
they won't appear in the assignee picker. Reassign from My Tasks → click the
task name → pencil icon next to Assigned To.

**Support:** portal → More → Support → describe the issue and pick a category.
Email confirmation on submission; CSGF typically responds within 1-2 business
days.

**Additional CSGF resources** (all new to the 2026-2027 cycle per the item list
doc): a
[full data-fields list](https://docs.google.com/spreadsheets/d/1yPT8M_2sAHdvlLL6SFM5XZICSjsUiFxJOGYz2tP3CBI)
and a sample all-in-one template; walkthrough videos are linked from the guide
and from the Salesforce Portal home page (bottom left).
