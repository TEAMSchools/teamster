# document-the-model skill — design

Issue: #5434. Source handoff: the CARAT session on PR #5542.

## Goal

One skill that brings a dbt model family to a handover-ready state, and keeps it
there after changes. Two modes:

- **Document** — reference doc, dbt YAML descriptions that match the SQL, tests
  every layer requires, a known-issues list, and (if the user agrees) a skill
  for the family.
- **Update** — after a change to a documented family, re-run only the checks the
  change affects.

Out of scope: designing a new model before it exists. That is
`superpowers:brainstorming`. Document mode accepts a superpowers spec as source
material, so a model designed there arrives with its reasoning written down.

## Decisions

| Decision             | Choice                                                                                                                                                                                                       |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Scope                | dbt model families. Cube and Tableau appear only as named consumers.                                                                                                                                         |
| Dashboard vs process | Branch on the exposure in `src/dbt/**/models/exposures/*.yml`. A Tableau exposure gets one doc section per dashboard view. Anything else (a Google Sheet, an extract) gets process sections.                 |
| Tableau access       | Never call the Tableau MCP or load `tableau-workbook-xml` without the user's go-ahead. Both use a lot of tokens.                                                                                             |
| Family boundary      | Propose, then the user confirms. Default: walk back from the exposure and keep every model whose children are all inside the family. Shared upstreams get one line in the doc and are not audited or tested. |
| Family skill         | Propose what a skill would hold (sheet upkeep, yearly rollover, recurring checks, common questions), then ask. If nothing recurring is found, say so and propose no skill.                                   |
| Tests                | Propose from each model's grain and column types. Check each against prod. The user approves. A test that fails today is still added and the failure goes to "Known issues".                                 |
| Update trigger       | On request only. No hook.                                                                                                                                                                                    |
| Before/after history | In each family's own skill.                                                                                                                                                                                  |
| Build shape          | Entry `SKILL.md` plus `references/` plus `scripts/` (ICM inside the repo convention). Not a Workflow script: too many steps wait on the user. Not a single long file: that is the failure CARAT hit.         |

## Document mode flow

1. **Intake.** Ask for source material: a file dropped in scratch, a public URL,
   an org Drive file shared with the Codespaces account, or a superpowers spec.
   Ask whether the family has Google Sheet upkeep processes.
2. **Inventory.** Find the exposure and pick the dashboard or process branch.
   Walk the lineage, propose the boundary, wait for the user. List any existing
   reference doc and skill, with line counts per section.
3. **Reference doc.** Write it, or restructure an existing one, from the
   branch's outline. A cold Opus subagent reviews it against the SQL; verify
   every flag yourself before fixing.
4. **YAML audit.** Descriptions only. Inline for families of about five models
   or fewer; otherwise one Opus subagent per group of about six. Verify the diff
   is description-only, then `dbt parse --no-partial-parse`.
5. **Tests.** Propose, check against prod (rows vs distinct keys), get approval,
   add. Staging tests carry `severity: error`.
6. **"Probably harmless" checks.** Every suspected-harmless oddity gets a query,
   recorded in the commit message.
7. **Family skill.** Propose contents, ask. If approved, build in ICM shape and
   walk-test it.
8. **Close out.** Trunk on every changed file, `dbt parse`, commits that state
   what was verified, push, PR.

### Doc outlines

Both start: What it is → How it fits together (diagram) → Terms → Where the data
comes from (source, owner). Both end: Supporting models → Inputs (Google Sheets
and others) → Decisions → Known issues, need to fix → Yearly upkeep.

- Dashboard branch middle: one section per view — What it shows / Grain / Reads
  / Worth knowing.
- Process branch middle: What triggers it → Inputs → Steps → Outputs (where they
  land, who reads them) → Who runs it and when.

Public-page rules for both: no internal sheet URLs or IDs, no emails, no student
data, no small-cell counts, no counts that go stale. The page goes in the
`mkdocs.yml` nav.

## Update mode flow

Take `git diff origin/main...HEAD`, filtered to the family's files, and map each
change:

| Change                        | Re-run                                                                |
| ----------------------------- | --------------------------------------------------------------------- |
| New or renamed column         | YAML, the doc sections that mention it, tests on it                   |
| Join, filter, or grain change | Grain check against prod, cold review of the affected doc sections    |
| New view, sheet tab, or model | New doc section, boundary check, skill route, walk test               |
| SQL comment only              | `comment_only_diff.py`; warn that CI rebuilds the model's descendants |

## Rules that apply to every step

These go in `SKILL.md`, because each prevents a failure the CARAT session hit:

- Sheet changes go out as the whole tab or block, in a tab-separated file in the
  session scratchpad, handed over as a path with the sheet link and tab name.
  Never comma-separated, never pasted into chat.
- Read the source the user is editing (a Sheets external through ADC from
  Python), not a reshaped staging table.
- State a pipeline behavior only from code or a before/after observation, not a
  timestamp.
- Read the whole block before flagging a bug in it.
- No doc claim ships without the cold review.
- BigQuery time travel: one query per timestamp; 7 days back at most.

## Files

```text
.claude/skills/document-the-model/
  SKILL.md                     modes, route by step, the rules above, acceptance
  references/
    intake-and-inventory.md    steps 1-2
    reference-doc.md           step 3: both outlines, public-page rules, cold-review prompt
    yaml-audit.md              step 4: rules, group sizing, audit prompt, diff check
    tests-and-issues.md        steps 5-6
    model-skill.md             step 7: proposal, ICM shape, split procedure, walk-test prompt
    update-mode.md             the change table in detail
  scripts/
    split_skill.py             verbatim split of an oversized skill, lines in = lines out
    check_links.sh             resolve every relative link in a skill or doc
    comment_only_diff.py       prove a SQL edit is comment-only
```

## Testing

Per `superpowers:writing-skills`:

- **RED.** A cold Sonnet subagent with no skill plans "document the athletic
  eligibility tracker". Record which failure modes it hits.
- **GREEN, walk tests.** Three cold Sonnet subagents, planning only: document
  athletic eligibility; add a column to a documented model; restructure an
  oversized skill. Each passes with the entry file plus at most two more reads.
- **GREEN, real run.** Document mode on the athletic eligibility family
  (`int_students__athletic_eligibility`, `rpt_gsheets__athletic_eligibility`) in
  a separate PR. It passes on the acceptance list in #5434.
- **REFACTOR.** Fixes the real run exposes land on this skill's PR; walk tests
  re-run after each fix.
- Scripts get pytest-style checks run by hand: `split_skill.py` on a fixture
  with `##` inside a fenced block; `comment_only_diff.py` on a comment-only and
  a logic change.

## Acceptance

- Walk tests pass (entry plus at most two reads).
- The athletic eligibility run passes: cold review finds no wrong claims after
  fixes, YAML diff is description-only apart from listed intentional changes,
  `dbt parse` and trunk pass, every missing uniqueness test is added or listed
  as a known issue.
- Trunk passes on every file in this PR.
