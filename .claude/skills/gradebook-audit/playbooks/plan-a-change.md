# START HERE: making a change to this model

If you have been asked to change anything in this pipeline (add/remove/edit a
flag, add a region, change a threshold, refactor a model, or anything else),
work through this before editing any SQL. Do not jump straight to a playbook —
those are the _how_; this is the _what and whether_. This matters most when you
did not build this model: it forces the questions and the impact checks a
newcomer would otherwise miss.

## 1. Confirm the change with the requester

Pin down the grain (student / section-category / teacher-quarter), the specific
flag / region / threshold, and the expected effect on the dashboard output —
more or fewer rows, a new column, changed booleans, or none for a pure refactor.
Do not edit until the change is unambiguous and the requester has confirmed the
intended output effect.

## 2. State which of these the change could break, and how you will check each

The risks below are specific to this model. Everything about dbt lineage, build
methodology and review flow lives in the skills and CLAUDE.md that already cover
it, and is not repeated here.

- the **4-row category floor** — every section × quarter must keep exactly 4
  `category_summary` rows;
- **grain changes cascade** — a grain change in any scaffold breaks every
  downstream join and must be threaded through all consumers before a full chain
  build is valid, so build the affected models one at a time and never cascade a
  downstream build mid-refactor;
- **uniqueness tests and contracts** on every affected model; a refactor that
  should not change output gets a byte-identical before/after comparison;
- the two **health columns** (`is_healthy_gradebook_all_flags` /
  `_excl_comments`) and the **broadcast** section-flag booleans — a new/removed
  flag usually has to thread into these;
- **PII** — student-level data stays in
  `int_extracts__gradebook_audit_student_flags` and the gsheets report; it must
  never reach `rpt_tableau__gradebook_audit`;
- the **layering rule** — reports (`rpt_`) must not read other reports; shared
  logic lives in the intermediate;
- the **summer-toggle** state (see the rollover playbook);
- both **exposures** — the Tableau workbook and the Google Sheet each consume an
  output of this pipeline.

To map what feeds and consumes a model you plan to touch, use the lineage
procedure in [`../references/data-model.md`](../references/data-model.md) rather
than editing against the one file in front of you.

## 3. Implement via the playbook that matches the change

- add/remove/edit a flag → [`change-a-flag.md`](change-a-flag.md)
- add a region → [`add-a-region.md`](add-a-region.md)
- roll T&L's expectations over to a new year →
  [`academic-year-rollover.md`](academic-year-rollover.md)
- change a hardcoded threshold, or need the current lineage/refs →
  [`../references/data-model.md`](../references/data-model.md)
- change, build, or deploy the PowerSchool plugin itself →
  [`maintain-the-plugin.md`](maintain-the-plugin.md)
- propagate a plugin or skill change to Teaching & Learning →
  [`ship-a-skill-update.md`](ship-a-skill-update.md)
- update a published Sheet's source/report pair →
  [`../references/published-sheets.md`](../references/published-sheets.md)

**Sections 1 and 2 are about dbt models.** If what you were asked to change is
the PowerSchool plugin itself, the end-user skill, or a published Sheet — and
touches no dbt model — go straight to the matching entry above; there is no dbt
lineage to map and no category floor to protect.

**A misbehaving flag is a bug, not a change.** If a flag fires when it shouldn't
or doesn't fire when it should, use [`debug-a-flag.md`](debug-a-flag.md) with
the `superpowers:systematic-debugging` skill instead of this gate.
