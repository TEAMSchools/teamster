---
name: gradebook-audit
description: >-
  Use when any question or task touches the gradebook audit pipeline end to end:
  the dbt models and dashboards, the PowerSchool Gradebook Audit plugin,
  shipping a change to the gradebook-expectations-upload end-user skill, or the
  published Google Sheet pairs it feeds. Triggers: explaining the model, listing
  refs/lineage/sources for the gradebook audit dashboard, adding/removing a
  flag, adding a region, debugging a flag that isn't firing, rolling the
  assignment expectations over to a new year (turning T&L's expectations sheet
  into U_EXPECTATIONS count rows to upload to PowerSchool), changing or
  deploying the `ps-plugins/gradebook-audit/` plugin, bumping or distributing a
  new version of the gradebook-expectations-upload skill, a change to a
  gradebook audit IMPORTRANGE/Reports sheet pair, or working on
  rpt_tableau__gradebook_audit or rpt_gsheets__gradebook_audit_student_flags and
  their upstream models.
---

# Gradebook Audit Data Model

This skill owns the whole chain, not just the dbt layer: (1) the dbt models and
the Tableau/Sheets dashboards, (2) the PowerSchool Gradebook Audit plugin that
manages `U_EXPECTATIONS`, (3) propagating a change to the
`gradebook-expectations-upload` end-user skill that Teaching & Learning runs,
and (4) the published Google Sheet pairs the pipeline feeds. One skill knowing
how all four fit together is the point — the alternative is three or four places
each knowing a third and drifting apart.

## Always read first

Before answering any question or making any change, read the reference doc. It
is the authoritative source for lineage, flag definitions, scaffold structure,
and configuration behavior. The spec covers AY 2026-2027 design decisions.

- Reference doc:
  [`docs/models/gradebook-audit-data-model.md`](../../../docs/models/gradebook-audit-data-model.md)
- Design spec:
  [`docs/superpowers/specs/2026-05-14-gradebook-audit-ay2627-design.md`](../../../docs/superpowers/specs/2026-05-14-gradebook-audit-ay2627-design.md)
- Implementation plan:
  [`docs/superpowers/plans/2026-05-14-gradebook-audit-ay2627-revamp.md`](../../../docs/superpowers/plans/2026-05-14-gradebook-audit-ay2627-revamp.md)

**Key gotcha:** `academic_year` stores the STARTING year. AY 2026-2027 =
`academic_year = 2026`. Confirm this with the user before generating any data.

## Before changing anything

Any change to this pipeline — a flag, a region, a threshold, a refactor — starts
at [`playbooks/plan-a-change.md`](playbooks/plan-a-change.md), not at the
specific playbook below. That file is the gate: it forces the clarifying
questions and the impact checks a newcomer would otherwise miss. The playbook
below is the _how_; `plan-a-change.md` is the _what and whether_.

## Routing

| Task                                                                                                | Read                                                                         |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Any change to the pipeline — read this first, before the row below that matches your change         | [`playbooks/plan-a-change.md`](playbooks/plan-a-change.md)                   |
| Add or remove a flag (student-, assignment-, or category-level)                                     | [`playbooks/change-a-flag.md`](playbooks/change-a-flag.md)                   |
| Bring a new region's PowerSchool instance into the audit                                            | [`playbooks/add-a-region.md`](playbooks/add-a-region.md)                     |
| Roll T&L's assignment expectations over to a new year (the PS plugin / `U_EXPECTATIONS` upload)     | [`playbooks/academic-year-rollover.md`](playbooks/academic-year-rollover.md) |
| Work on the dashboard during summer, before the new year's PowerSchool data exists (the dbt toggle) | [`references/summer-toggle.md`](references/summer-toggle.md)                 |
| A flag is firing when it shouldn't, or not firing when it should                                    | [`playbooks/debug-a-flag.md`](playbooks/debug-a-flag.md)                     |
| Explain why an undocumented filter, column, or threshold exists                                     | [`playbooks/explain-a-decision.md`](playbooks/explain-a-decision.md)         |
| List refs/lineage/sources for the dashboard, explain the model, or look up a configurable threshold | [`references/data-model.md`](references/data-model.md)                       |
| Change, build, or deploy the PowerSchool plugin itself                                              | [`playbooks/maintain-the-plugin.md`](playbooks/maintain-the-plugin.md)       |
| Get a plugin or skill change to Teaching & Learning (organization skills or per-user zip)           | [`playbooks/ship-a-skill-update.md`](playbooks/ship-a-skill-update.md)       |
| A published Sheet's source/report pair needs a matching update, or one looks out of sync            | [`references/published-sheets.md`](references/published-sheets.md)           |
