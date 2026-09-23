# START HERE: making a change to this model

If you have been asked to change anything in this pipeline (add/remove/edit a
flag, add a region, change a threshold, refactor a model, or anything else), run
these steps **in order before editing any SQL**. Do not jump straight to a
playbook — those are the _how_; this is the _what and whether_. This matters
most when you did not build this model: it forces the questions and the impact
checks a newcomer would otherwise miss.

1. **Clarify the change with the requester — do not assume.** Invoke the
   `superpowers:brainstorming` skill (`Skill` tool) and use it to pin down, one
   question at a time: exactly what should change, why, at which grain (student
   / section-category / teacher-quarter), which specific flag / region /
   threshold, and the expected effect on the dashboard output (more or fewer
   rows? a new column? changed boolean values? none — a pure refactor?). Do not
   edit until the change is unambiguous and the requester has confirmed the
   intended output effect.

2. **Read the reference doc** (required by "Always read first" in `SKILL.md`) so
   you know the current lineage, grain, and invariants before you reason about
   impact.

3. **Map the impact up- and downstream.** For every model you plan to touch,
   enumerate what feeds it and what consumes it — never edit against only the
   one file in front of you:

   - `mcp__dbt__get_model_parents` and `mcp__dbt__get_model_children` (or
     `mcp__dbt__get_lineage`) on each target model.
   - Cross-check against this skill's "List refs, lineage, or sources" procedure
     (the exposure file) and the reference doc's lineage diagram.
   - Invoke `dbt:using-dbt-for-analytics-engineering` (`Skill` tool) for the
     build-and-validate methodology.

4. **Flag the model-specific risks to the requester before implementing.** State
   which of these the change could break, and how you will check each:

   - the **4-row category floor** — every section × quarter must keep exactly 4
     `category_summary` rows;
   - **grain changes cascade** — a grain change in any scaffold breaks every
     downstream join and must be threaded through all consumers before a full
     chain build is valid;
   - **uniqueness tests and contracts** on every affected model;
   - the two **health columns** (`is_healthy_gradebook_all_flags` /
     `_excl_comments`) and the **broadcast** section-flag booleans — a
     new/removed flag usually has to thread into these;
   - **PII** — student-level data stays in
     `int_extracts__gradebook_audit_student_flags` and the gsheets report; it
     must never reach `rpt_tableau__gradebook_audit`;
   - the **layering rule** — reports (`rpt_`) must not read other reports;
     shared logic lives in the intermediate;
   - the **summer-toggle** state (see the rollover procedure);
   - both **exposures** — the Tableau workbook and the Google Sheet each consume
     an output of this pipeline.

5. **Implement** via the specific playbook (add/remove/edit a flag:
   `change-a-flag.md`; add a region: `add-a-region.md`; or the rollover:
   `academic-year-rollover.md`), following the grain rules it gives.

6. **Validate, then get a review.** Build the affected models one at a time
   (never cascade a downstream build mid-refactor), confirm the checks that
   apply (uniqueness tests pass, the 4-row floor holds, and — for a refactor
   that should not change output — a byte-identical comparison of before/after),
   then invoke the `superpowers:requesting-code-review` skill (`Skill` tool)
   before opening or updating the PR.

**For a flag that is misbehaving** (firing when it shouldn't, or not firing when
it should) rather than a requested change, this is a bug, not a feature: use
[`debug-a-flag.md`](debug-a-flag.md) together with the
`superpowers:systematic-debugging` skill.
