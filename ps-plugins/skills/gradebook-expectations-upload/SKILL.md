---
name: gradebook-expectations-upload
version: "1.0.0"
description: >-
  Use when the gradebook audit's weekly assignment expectations need to go into,
  or be diagnosed in, PowerSchool. Triggers: "we need to load the gradebook
  expectations", "roll the gradebook expectations over to the new year", "T&L
  decided the counts for Q2", "the audit is showing last year's expectations",
  "why isn't the gradebook audit updating", "the dashboard numbers look wrong,
  can you help me figure out why", "generate the U_EXPECTATIONS files". Reads
  the Academics planning sheet, matches it to PowerSchool's calendar, and either
  produces upload CSVs, walks through the PowerSchool plugin, or diagnoses a
  mismatch — depending on which of the three playbooks below fits.
---

# Gradebook Expectations Upload

This turns the weekly assignment counts Teaching & Learning decide into what
PowerSchool's Gradebook Audit plugin needs. The plugin is what lets school-level
staff manage `U_EXPECTATIONS` themselves, without going through the data team
for every change — that's the whole point of this skill existing: **you are the
bridge** between Academics' human-readable planning calendar and PowerSchool's
date-blind, week-number-based table. The gradebook audit dashboard compares what
teachers actually entered against these counts, so a wrong count makes the
dashboard wrong — quietly, with no error anywhere.

## Which of these three is this?

| The person is asking...                                                                      | Playbook                                                 |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| Start a new school year — load the whole year's calendar into PowerSchool for the first time | [`playbooks/rollover.md`](playbooks/rollover.md)         |
| A quarter (or a few) is newly decided or changed mid-year and needs to go in/update          | [`playbooks/refresh.md`](playbooks/refresh.md)           |
| "Why does the dashboard look wrong / why isn't it updating / help me figure this out"        | [`playbooks/troubleshoot.md`](playbooks/troubleshoot.md) |

If it's ambiguous which one fits, ask — but most of the time the person's own
phrasing already tells you (see the trigger phrases above). Don't ask which
quarters, which regions, or how far to go beyond what's needed to pick the right
playbook; each playbook tells you how to determine the rest from the sheets
themselves.

Every playbook leans on the same shared knowledge, in `references/`:

- **`references/sheets.md`** — the two spreadsheets, their columns, which tab
  feeds which PowerSchool instance, and why the plugin has no `academic_year` or
  `region` field.
- **`references/week-matching.md`** — how the dashboard actually reads the data,
  and the date → PowerSchool-week-number translation that is this skill's core
  value.
- **`references/csv-format.md`** — the CSV shape the plugin requires, and the
  checks (including a sanity-check against what's already live) to run before
  anything is uploaded.
- **`references/powerschool-navigation.md`** — the verified, step-by-step manual
  for the plugin itself: logging in, deleting, uploading, fixing a single row,
  and the next-day verification.

## Stop and escalate

Regardless of which playbook you're in, stop and contact the data team if:

- A check fails and you cannot see why.
- A delete succeeds but the load fails. **Say so immediately, not tomorrow** —
  the dashboard now has no expectations for those weeks, for every school in
  that region. Rebuild the missing rows by hand (`powerschool-navigation.md`,
  single-row fix) rather than leaving the region wrong overnight, and do not
  re-run Replace.
- The numbers look implausible — counts falling as a quarter progresses, or a
  week far out of line with its neighbours. These are counts a person typed, and
  a typo here misreports every teacher in a region.
- A troubleshooting session (`playbooks/troubleshoot.md`) turns up something
  systemic rather than a one-off.

## Notes for maintainers

- The Academics sheet is where a year's counts are decided, and its tabs are
  renamed each year (`- Q1`, `(Q2-4 under construction)`). Match tabs by region
  and level, not by exact tab name.
- **Access control on the single-row pages is a known gap.** Group membership is
  not what decides who can reach them today. The plugin's own README in the
  `TEAMSchools/teamster` repo carries the detail — it is not a file in this
  skill. `powerschool-navigation.md`'s single-row fix now sends people to those
  pages, so it is worth closing.
- **`rpt_gsheets__gradebook_audit_student_flags`** is part of the gradebook
  audit dashboard, downstream of this process. It exists because plugin data
  reaches PowerSchool, but it is technically independent — not an input, not a
  check.
- The data-team counterpart to this skill is `gradebook-audit` in the
  `TEAMSchools/teamster` repo. It holds the dbt lineage, the verification query,
  and the reasoning behind the replacement rule. It deliberately does not repeat
  the generation steps — those live here, so the two cannot drift.
- The per-quarter delete in `powerschool-navigation.md` leans on three
  behaviours of `gradebook_expectations.html`: the filter hides and unchecks
  non-matching rows, the header checkbox checks only visible rows, and Delete
  Selected acts only on checked rows. Replace mode, by contrast, reads the
  unfiltered row set. If a future plugin version adds a real scoped-delete
  control, replace that dance with it.
- This skill was restructured from a single flat file into this
  playbook/reference split so that a third intent (troubleshooting) could be
  added without threading a diagnostic flow through steps meant for building and
  uploading. If a fourth distinct intent shows up, give it its own playbook
  rather than branching inside an existing one.
