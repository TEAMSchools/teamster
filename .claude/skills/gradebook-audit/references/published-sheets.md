# Reference: The published Google Sheet pairs

**Procedure and the per-change table live in
[`docs/guides/google-sheets.md`](../../../../docs/guides/google-sheets.md)** —
read "Publishing a warehouse view to a Google Sheet" there before touching
either sheet. This file only says which models and tabs are specific to the
gradebook audit; it does not repeat the general rules.

## The shape: every published view is two sheets

1. **IMPORTRANGE Sources** — the Connected Sheets extraction. Refresh schedules
   are programmed here and only here.
2. **Reports** — what the actual user opens, one tab per source tab with a
   friendly name, pulling from the source sheet with `IMPORTRANGE` and nothing
   else.

**A change to either copy has to be made in both.** Nothing in the pipeline
creates a tab or widens an `IMPORTRANGE` range for you — the Dagster exposure
asset is a marker that writes nothing, so the dbt model landing in BigQuery is
the start of that job, not the end of it. A column added to the model is the
dangerous case: see `docs/guides/google-sheets.md`'s table for exactly what to
do in each sheet for each kind of change (new model, column added/removed, tab
renamed, model retired) — the column case is the one that fails silently, so
read that warning there rather than skipping to the table below.

## The gradebook audit's tab pairs

The upload-template exposure (`rpt_gsheets__gradebook_audit_template` in
`src/dbt/kipptaf/models/exposures/google-sheets.yml`) feeds the **Gradebook
Audit Template** sheet pair that the end-user skill's `references/sheets.md`
describes from the T&L side. Three dbt models sit behind three of its four
Reports tabs. **The IMPORTRANGE Sources tab names are short internal names, not
the model names** — do not rename a source tab to "match" its model; that is
exactly the action that returns `#REF!` in every downstream `IMPORTRANGE`.

| Model                                               | IMPORTRANGE Sources tab | Reports tab                  | What it holds                                                                                                                                                            |
| --------------------------------------------------- | ----------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `rpt_gsheets__gradebook_audit_all_weeks`            | `ps_all_weeks`          | `PS Full Calendar`           | Every school week of the current academic year, from `int_students__calendar_week` — not filtered to weeks already loaded into `U_EXPECTATIONS`.                         |
| `rpt_gsheets__gradebook_audit_current_expectations` | `ps_plugin_raw`         | `Plugin Data Raw`            | Passthrough of `stg_powerschool__u_expectations` — what's actually live in PowerSchool right now, per row, with who/when it was created or changed.                      |
| `rpt_gsheets__gradebook_audit_template`             | `ps_plugin_data`        | `Template QW-Date Crosswalk` | One row per region × school level × quarter × week, counts as `W`/`H`/`F`/`S` columns — the week-number translation between Academics' sheet and PowerSchool's calendar. |

**The fourth Reports tab, `PS Plugin CSV Template`, has no model behind it and
no IMPORTRANGE Sources counterpart.** It's the literal CSV header row PS
requires, kept there only so nobody retypes it by hand — nothing refreshes it
automatically, so if the plugin's accepted header ever changes (tracked by
`build_plugin.py`'s CSV-header contract check, see `maintain-the-plugin.md`),
this tab has to be updated by hand, in the Reports copy only.

The other exposure this skill owns,
`rpt_gsheets__gradebook_audit_student_flags`, is a single-tab sheet (ops
follow-up on flagged students) and follows the same source/report pairing — see
`docs/guides/google-sheets.md` for the mechanics; there's nothing audit-specific
to add beyond what's in the table above.
