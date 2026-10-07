# Editing Tableau workbooks as XML

Handoff notes for building a skill. Everything here was learned by editing the
`Academic & Gradebook Health Suite` workbook directly as `.twb` XML, publishing
to a scratch Tableau project, and rendering the result. It is written for an
agent, not a person: dense, symptom-first, and explicit about what is verified
versus inferred.

## Read this first

Three rules explain most of the time lost. If the skill teaches nothing else,
teach these.

### 1. A passing checker is not a working dashboard

Every serious defect in this project passed XML validation, passed a schema
check, and published to Tableau Server without complaint. They were found by
looking at a rendered image. In one build, four separate defects survived a full
checker suite that included nine mutation tests:

- Two headline numbers rendered as `####` (text did not fit its box).
- A five-entry color legend displayed three of them.
- Two row labels clipped mid-word.
- Two dynamic text lines rendered blank.

The XML was valid every time. **Render and look.** Where a behavior cannot be
rendered — a click, a hover — say so out loud rather than inferring it.

### 2. Tableau Desktop and Tableau Server disagree about what is valid

Server is permissive. It accepted and rendered workbooks that Desktop refused to
open. Desktop validates against a content model; Server largely does not. A
workbook that publishes and renders can still be unopenable by the person who
owns it.

Consequence: publishing successfully proves nothing about Desktop. The checks in
`scripts/check_twb.py` exist because each one corresponds to a Desktop refusal
that Server had already waved through.

### 3. The tests are more likely to be wrong than the edits

Across this project, nearly every artifact was correct on first or second
delivery. Nearly every serious review finding was against a _test_ that would
have passed something broken:

- A geometry checker with 4,500 units of tolerance against the 4,445-unit bug it
  existed to catch.
- A structure assertion that passed a duplicated zone, a re-parented zone, and a
  reordered zone.
- The same assertion, after hardening, still passing a card nested inside
  another card.

Budget review effort accordingly. When an assertion passes, ask what broken
input it would also pass, then build that input and run it.

## What is in here

The skill built from these notes is now the canonical copy:
`.claude/skills/tableau-workbook-xml/SKILL.md` and its `references/`. The six
numbered files below are pointer stubs kept so links resolve; edit the skill
reference, not the stub.

| File                                             | Now lives at                                                                                                                       |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| [01-content-models.md](01-content-models.md)     | [`references/content-models.md`](../../.claude/skills/tableau-workbook-xml/references/content-models.md)                           |
| [02-dynamic-text.md](02-dynamic-text.md)         | [`references/dynamic-text.md`](../../.claude/skills/tableau-workbook-xml/references/dynamic-text.md)                               |
| [03-layout-and-zones.md](03-layout-and-zones.md) | [`references/layout-and-zones.md`](../../.claude/skills/tableau-workbook-xml/references/layout-and-zones.md)                       |
| [04-formatting.md](04-formatting.md)             | [`references/formatting.md`](../../.claude/skills/tableau-workbook-xml/references/formatting.md)                                   |
| [05-build-workflow.md](05-build-workflow.md)     | `SKILL.md` "The loop" and [`references/build-workflow.md`](../../.claude/skills/tableau-workbook-xml/references/build-workflow.md) |
| [06-failure-catalog.md](06-failure-catalog.md)   | [`references/failure-catalog.md`](../../.claude/skills/tableau-workbook-xml/references/failure-catalog.md)                         |
| [scripts/](scripts/)                             | Still here: runnable checkers and helpers, with a README. The skill references them by this path                                   |

## Provenance and confidence

Claims are marked in each file:

- **Verified** — observed directly, usually in a render or a Desktop error.
- **Inferred** — consistent with observation but not directly tested. Several
  inferences in this project turned out to be wrong; treat them as hypotheses.

Two inferences that failed, recorded so the skill can warn about the pattern:

- A parameter placeholder resolves in a worksheet title. It was assumed to
  therefore resolve in a mark label. It renders blank there.
- A tooltip form found in the workbook was assumed to work because it was
  present. Presence in a file is not evidence of rendering.

The generalizable lesson: **evidence from one Tableau surface does not transfer
to another surface.** Probe each one.

## Where this lives

Deliberately **not** in the `mkdocs.yml` nav, following the same precedent as
`docs/superpowers/`: it is working material for building a skill, not published
engineering reference. It is reachable by URL. Add a nav entry if it outlives
that purpose.

## Scope

This is about hand-editing workbook XML. It assumes:

- The workbook is downloaded with `tableauserverclient`, edited as text,
  repacked into a `.twbx`, and published to a scratch project.
- Nothing is ever published directly to a production project.
- Verification is a render plus a set of assertion scripts, not Desktop.

It does not cover Tableau Desktop authoring, the REST API beyond
publish/download/render, Prep, Pulse, or extract internals.
