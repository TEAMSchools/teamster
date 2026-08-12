# Dashboard help-article pipeline — design

Refs #4843

## Problem

School-based staff use Tableau dashboards daily with no help-desk documentation.
Tickets that reach the Data team are frequently navigational ("where do I find
my school's number") rather than data defects — questions an article would
answer.

Writing ~30 articles by hand is not going to happen. Nor is maintaining them: a
dashboard changes, the article silently goes stale, and a wrong article is worse
than none. The pipeline has to make the first draft nearly free and the update
path a pull request.

## Audience

**School-based staff** — principals, APs, teachers. Task-first: click-paths and
filter walkthroughs, not a field glossary. A reader is between classes and wants
to finish something, not understand the system.

This decision drives everything downstream. It is why the workbook XML matters
more than the dbt lineage, and why screenshots are load-bearing enough to be
worth the PII problem they create.

## Inputs

Four sources. Only the first needs a human.

| #   | Input                                                                      | Provides                                                                                                                                                           | Cost                                                |
| --- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------- |
| 1   | `.twb` XML from the packaged workbook                                      | Filter names, defaults and scope; parameter allowed values; dashboard-to-worksheet composition; calculated-field formulas; tooltip strings; filter and URL actions | One manual download per dashboard                   |
| 2   | Tableau MCP `list-views`, `get-workbook`, `get-datasource-metadata`        | View inventory, owner, datasource field names and descriptions                                                                                                     | Free, re-runnable                                   |
| 3   | `rpt_tableau__<name>` model YAML + `docs/models/<dashboard>-data-model.md` | Authoritative metric definitions and known caveats                                                                                                                 | Free, already written for FRESH and gradebook audit |
| 4   | `get-view-image` with `viewFilters`                                        | Aggregate-safe screenshots                                                                                                                                         | Free; PII-gated, see below                          |

### Why the XML is not redundant

`get-workbook` returns REST metadata about views. It does **not** return the
workbook definition, so it carries no formulas, no filter defaults, no parameter
domains and no tooltip text. Those are precisely the strings a task-first
article must reproduce exactly. The XML is the only source for them.

### Why not a video walkthrough

Rejected as the primary input. Claude Code cannot ingest video, so it would need
frame extraction plus a transcript before yielding anything. Transcripts are
lossy on exact labels — "the school filter" instead of `Reporting School Name` —
which is the one thing the article cannot get wrong. And a recording is not
diffable, so every dashboard change means re-recording rather than a PR.

Video remains a reasonable _optional_ capture of owner intent, which no metadata
contains. It is not part of v1.

## Approach

Three shapes were considered.

- **A — skill only.** A Claude Code skill drafts Markdown into the repo; a human
  publishes in-session via the Zendesk MCP.
- **B — A plus CI publish.** A GitHub Action renders and publishes on merge.
- **C — Dagster asset.** Articles as assets, with a sensor on workbook
  `updatedAt` regenerating drafts automatically.

**Selected: A.** The template is the hard part and will be rewritten several
times after the first real article; A gets there with zero infrastructure. B's
only gain over A is publish-on-merge, since committing the Markdown already
provides diffing and review — a large build for a button at ~30 dashboards that
change a few times a year. C adds staleness detection this cadence does not
need, introduces an LLM-in-Dagster pattern the repo does not have, and fits the
mandatory human review step badly.

B and C are explicitly good later augmentations, not rejected ideas. The front
matter below is designed so both stay cheap to add.

**Accepted risk:** nothing detects a dashboard changing under a stale article.
That bites at ~200 articles, not ~30. If it bites, the cheap fix is a scheduled
agent diffing workbook `updatedAt` against front matter — not C.

## Repository layout

Markdown is the source of truth; Zendesk is a render target.

```text
docs/help-center/
  gradebook-audit.md
  gradebook-audit.assets/
    01-overview-aggregate.png     # get-view-image, regenerable
    02-flag-detail-redacted.png   # human crop, not regenerable
```

`docs/help-center/` is excluded from the MkDocs nav, following the existing
`docs/superpowers/` precedent for Markdown in `docs/` that is not a published
page. Per `docs/CLAUDE.md`, omission from `mkdocs.yml` `nav:` is sufficient on
its own: such pages stay reachable by URL but do not appear in navigation, and
no further configuration is required.

### Front matter

```yaml
tableau_workbook_id: <luid>
tableau_workbook_updated_at: <iso8601> # staleness check keys off this
zendesk_article_id: <id> # empty until first publish
zendesk_section_id: <id>
dbt_models: [rpt_tableau__gradebook_audit]
design_snapshot: 2026-08-11 # zendesk-design import date
last_reviewed_by: <owner>
last_reviewed_at: <date>
```

## Design-system integration

The visual system already exists as the `zendesk/` subsystem of the
`KIPP NJ | Miami Design System` Claude Design project
(`1916b968-b9bd-4eeb-9bb5-b23d2f407fb6`), reachable via the `DesignSync` tool.

It is a rigorous, sanitizer-aware spec, and it resolves questions this design
would otherwise have had to invent answers to:

- Zendesk article HTML is **email-grade**: no `<style>`, no `var()`, no flex or
  grid, `margin` only on `<table>`.
- Therefore every block is a `<table>` with padding on the `<td>`, and inside a
  `<td>` you use `<div>`, never `<p>` — `margin:0` on a `<p>` is _stripped_, so
  the browser default returns on the published page and the block inflates.
- Literal hex values only; the design tokens cannot be referenced.
- Fonts **are** controllable, via inline `font-family` on each block's outermost
  element.
- Sanitizing is invisible: unsafe HTML stays in the stored article but is
  omitted from the response, so the editor looks correct and the published page
  does not.

### Two-stage guidance, two documents

| Stage  | Output                          | Governed by                |
| ------ | ------------------------------- | -------------------------- |
| Draft  | Markdown in `docs/help-center/` | Voice supplement (words)   |
| Render | Zendesk-safe HTML               | `zendesk-design/` (visual) |

The design system is invoked at **render**, not draft. This keeps the Markdown
clean and portable, and lets a design-system change re-render every article
without re-drafting any of them.

### Snapshot, not a live read

The six `zendesk/` files are imported to
`.claude/skills/dashboard-help-article/references/zendesk-design/` as a pinned
snapshot, with `PROVENANCE.md` recording the project id, source paths and import
date. Claude Design stays upstream source of truth; the snapshot makes rendering
reproducible without a per-article network call, and the `design_snapshot` front
matter field records which snapshot an article was rendered against.

**The local snapshot is prettier-formatted, not verbatim** — the `trunk fmt`
pre-commit hook rewrote it, and a `lint.ignore` exclusion was declined for now.
It stays a correct reference for what the markup should contain, but the live
Claude Design snippet library is the place to copy paste-ready HTML from. Full
detail and the restore procedure are in `PROVENANCE.md`.

### Invocation

Skills cannot invoke each other programmatically. The skill body states it
imperatively: before rendering HTML, read `references/zendesk-design/README.md`.
Two notes:

- Subagents do not auto-invoke skills. Any dispatched drafting or rendering step
  must name the exact reads in its prompt.
- A more deterministic option exists if this proves unreliable: a PreToolUse
  hook on the `docs/help-center/` path, mirroring the existing `tool-gotchas.sh`
  pattern that injects `.claude/context/<server>.md`. Deferred — the instruction
  is expected to suffice, and hook scripts require manual application.

## Article template

The design system mandates an outer article structure; the task-first sections
for school staff nest inside its body. Merged:

| Order | Block                                | Content                                                                                   |
| ----- | ------------------------------------ | ----------------------------------------------------------------------------------------- |
| 1     | (no `<h1>`)                          | Zendesk renders the title. Never repeat it in the body.                                   |
| 2     | Summary panel                        | What this tells you, in 2–3 sentences. Who it is for, and what row-level access applies.  |
| 3     | In this article                      | Required — this template always exceeds three sections.                                   |
| 4     | `<h2>` Finding your school's numbers | The primary click-path as numbered steps, one action each.                                |
| 5     | `<h2>` The tabs                      | One short block per dashboard tab: what it answers, when to open it.                      |
| 6     | `<h2>` What each number means        | One plain sentence per metric. **Four columns maximum** — tables do not reflow on mobile. |
| 7     | `<h2>` Reading it correctly          | Caveats that change interpretation, as Note/Warning callouts.                             |
| 8     | `<h2>` When it updates               | Refresh cadence.                                                                          |
| 9     | Related articles                     | Closing links, including how to file a ticket.                                            |

No FAQ section in v1 — see _Deferred_ below.

## Voice supplement

The design system's own Voice section already covers second person imperative,
one action per step, naming UI elements exactly in `<strong>`, `<kbd>` for keys,
`<code>` for literal values, ending a procedure with the confirmation the reader
should see, and banning emoji plus "simply / just / easy".

Notably its "name UI elements exactly as they appear" rule is the same
verbatim-label discipline this pipeline needs. The supplement therefore does not
restate voice — it adds only what is specific to dashboards, at
`references/voice-supplement.md`:

**Do not explain the pipeline.** An agent reading dbt model docs will want to
narrate lineage. School staff do not need to know a number arrives via
PowerSchool and four dbt models. Name a source system only when it changes what
the reader should do — "fix this in PowerSchool; editing here will not stick"
earns its place; "sourced from `int_powerschool__attendance`" never does.

**Word swaps**, for the analytics vocabulary that leaks in from inputs 2 and 3:

| Don't                                  | Do                            |
| -------------------------------------- | ----------------------------- |
| grain, granularity, row-level          | "one row per student per day" |
| null, missing values                   | blank                         |
| upstream, materialized, scaffold       | (cut)                         |
| the selected entity                    | your school                   |
| records                                | students, or staff            |
| deduplicated                           | counted once                  |
| leverage, utilize, surface, actionable | use, show, (cut)              |

**Say what a number counts before what it means.** "Counts students enrolled on
the last school day of the month" beats "monthly enrollment metric."

**Length ceiling: about two laptop screens.** A dashboard needing more is a
signal it wants two articles, or that the dashboard needs fixing.

## Guardrails

1. **Verbatim-label rule.** Every UI label is copied character-for-character
   from the XML, never paraphrased. Top failure mode: an article saying "the
   School filter" when the control reads `Reporting School Name` sends the
   reader hunting and produces the ticket the article was meant to prevent.
1. **Every definition traces to a source.** Each metric line carries an HTML
   comment naming its origin — dbt column description, calculated-field formula,
   or data-model doc line — stripped at render. Where no source exists, the
   draft emits a `> **Owner: confirm**` callout instead of a plausible guess.
   This is the counterweight to the rubber-stamp risk inherent in
   owner-reviews-a-strawman: it points the reviewer's attention at exactly the
   lines that need it.
1. **No invented refresh cadence.** It comes from the Dagster schedule or dbt
   job building the `rpt_tableau__` model, or it is an owner-confirm callout.
1. **PII gates.** The `.twbx` and any extract stay in `.claude/scratch/`,
   gitignored — a packaged workbook can carry real student rows. No
   student-level view is rendered. Every generated image is reviewed before
   upload. Redaction is explicitly the human's job; the skill must not claim it
   can redact.
1. **The skill drafts and renders; it does not publish.** Publishing is a
   separate deliberate step.

### Pre-publish gate

Mechanical, and worth automating early:

- Every filter and tab name in the article appears verbatim in the XML.
- Every named metric has a traced source.
- Zero unresolved `Owner: confirm` callouts.
- No `<p>` inside a `<td>`; no `var()`; no `<style>`, `<button>` or `<svg>`.
- Data tables are four columns or fewer.
- **Verified on the published page, not the editor preview.**

The real test remains an AP reading it cold and completing the click-path
unaided.

## Screenshots

Aggregate-first, with human-redacted crops where an aggregate view cannot carry
the point.

**"Aggregate-safe" means:** no rendered mark, label, tooltip or table row in the
image corresponds to a single student. A school-level bar chart qualifies. A
student roster does not, and neither does a chart whose smallest bar is one
student — so check the underlying counts, not just the visual form. Rendered
images use the design system's `div` + `img` + caption `div` pattern, never
`<figure>` — its default `1em 40px` margin cannot be zeroed and would indent
every image 40px against the rest of the article.

## Open questions

1. **Is `kipp-help-center-theme.css` installed in the KIPP Guide theme?** If
   yes, the render can emit `<div class="kipp-callout kipp-callout--warning">`
   instead of ~300 characters of inline style per block. **Default assumption:
   not installed** — emit inline styles, which work either way. Confirming theme
   access is a cheap, high-value follow-up that shrinks article HTML roughly
   tenfold.
1. **Where do article images get hosted?** The Zendesk MCP exposes
   `create_article` and `update_article_translation` but **no article-attachment
   upload tool**. This is the one part of the pipeline needing real code,
   against the Zendesk Article Attachments REST API. It is also the only
   separable component here — everything else is skill instructions and
   Markdown, so the uploader can be sequenced as its own task, or deferred by
   publishing a text-only first article.
1. **Which Help Center section and permission group?** Resolve with
   `list_help_center_sections`, `list_permission_groups` and
   `list_user_segments` before the first publish.

## Deferred

- **FAQ from ticket mining.** `search_tickets` could derive real gotchas from
  what staff actually asked. Deliberately out of v1: shipping without a FAQ
  beats shipping a fabricated one, and mining is a better signal _after_
  articles exist, when it reveals what still generates tickets. Note the PII
  caution on ticket bodies.
- **Owner intake form.** The owner reviews a strawman rather than answering
  questions. Lowest friction; the traced-source guardrail above is what keeps it
  honest.
- **CI publish-on-merge (B)** and **Dagster staleness detection (C)**.

## Pilot

**The gradebook audit dashboard.** School-leader-facing, and it already has both
a 1,215-line data-model doc and a dedicated skill — so it exercises the
existing-docs input at full strength. If the pipeline cannot produce a good
article there, it will not anywhere.
