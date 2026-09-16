# Cube guidance packaging — design

Status: accepted. Anchored by
[#5348](https://github.com/TEAMSchools/teamster/issues/5348).

Implemented by two plans:

- `docs/superpowers/plans/2026-09-16-cube-description-correctness.md` (ships
  first, no dependency on the rest)
- `docs/superpowers/plans/2026-09-16-cube-guidance-packaging.md`

## The problem

The Cube assessment guidance works in exactly one place: a shared claude.ai
Project that three regional achievement directors use. Two markdown files load
there as Project knowledge, and a third block of text is pasted by hand into the
Project's custom-instructions field. Anyone outside that Project gets no session
protocol, no data-usage conventions, and no session record.

That blocks the roadmap. Grades and grade point average (GPA) are next, with
three to four power users, then operations. Every new domain would need its own
Project, its own uploaded copies, and its own hand-pasted instructions.

There is a second problem, and it is the one that reorders this work.

**The guidance leaks, and better delivery cannot fix it.** Across about ten
recorded sessions the protocol failed four times:

| Failure                                   | Recorded detail                                                                  |
| ----------------------------------------- | -------------------------------------------------------------------------------- |
| Participant name guessed instead of asked | 3 of the first 4 sessions; one guessed from a GitHub commit author               |
| Calibration record read inconsistently    | 3 sessions read the same week-end attendance record 3 different ways             |
| Student identifiers in chat               | 1 session printed 16 named students into chat after a valid authorization        |
| Session record filed repeatedly           | 1 session filed 7 times over 8 days, leaving 7 permanent files nobody can delete |

Every one of those happened while the guidance was loaded unconditionally as
Project knowledge **and** restated again in the Project's custom instructions.
That is the strongest delivery this platform offers. Delivery was saturated and
the protocol still leaked four ways, so the wording is the broken variable, not
the channel.

Two observations follow, and they set the whole shape of this work:

1. Repackaging alone would move a known-leaky protocol onto a **weaker** mount,
   because a skill loads only when Claude judges its description matches,
   whereas Project knowledge always loads.
2. The rewrite that fixes the wording makes the document **shorter**, not
   longer. Converting a recorded incident into a direct stop is the same edit as
   compressing it. Hardening and compression are one job, not two.

## Evidence base

Measurements below were taken from the working tree and re-verified on
2026-09-16 after commit `31c6faa9e` landed. Re-verify any number before acting
on it; this file will drift.

| Artifact                                                         | Measured                                                                                  |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md` | 367 lines, 3,115 words, 20,133 bytes                                                      |
| `src/cube/mcp/project_knowledge/assessment-cube-reference.md`    | 441 lines, 29,134 bytes, 7 sections                                                       |
| `src/cube/mcp/project_knowledge/README.md`                       | 71 lines, 3,406 bytes                                                                     |
| `src/cube/mcp/server.py`                                         | 569 lines, 23,260 bytes                                                                   |
| Full `meta` payload                                              | 161,663 bytes, 331 members, 6 views — overflows the tool-result budget and spills to disk |
| `student_assessment_scores_view` share of that payload           | 42,730 bytes                                                                              |
| Auto-generated `title` and `shortTitle` share                    | 19,446 bytes, 12 percent                                                                  |
| Member descriptions share                                        | 41,156 bytes, 25.5 percent                                                                |

Two facts about that payload matter for every placement decision below. First,
the payload already exceeds the tool-result budget, and issue #4470 recorded it
at about 135,000 characters on 2026-07-20, so it grew about 20 percent in five
weeks with no relocation at all. Second, the orchestrator mandates a
force-refresh of `meta` at session start with no view scoping, so every session
pays the full cost with the cache deliberately bypassed.

A claim worth recording because it was tested and held: **field descriptions do
reach the model verbatim.** They arrive at `cubes[].dimensions[].description`
and `cubes[].measures[].description`, inherited from the source cube through
`aliasMember`. `server.py` returns the raw body, and the view-filtered path
shallow-copies whole cube dictionaries. Zero of 327 descriptions were truncated.
The YAML channel works; it is simply full.

## Architecture

### Four layers, each carrying what only it can carry

```text
Organization instructions   always loaded, every user, every message, 3,000 chars
  └── names the skill and tells Claude to run it before the first data answer

cube-data-session (skill)   the protocol: gate, confidence, PII, session record
  └── domain-agnostic, reused unchanged by every future domain

<domain>-cube-conventions   routing and domain facts, one skill per domain
  └── opens with a pointer STEP back to cube-data-session

Cube YAML + MCP docstrings  field semantics and query mechanics
  └── reaches every consumer, propagates fastest, costs context every session
```

The layering is driven by two properties that differ sharply between channels.

**Propagation speed**, verified end to end:

| Channel                    | Path to the user                                                     | Staleness                                                                     |
| -------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Cube YAML                  | merge to `main`, Cube Cloud auto-redeploys, next `meta` call sees it | effectively zero                                                              |
| MCP tool docstring         | connector caches the tool list at connect time                       | unbounded, no version indicator, no push possible under `stateless_http=True` |
| Skill or Project knowledge | human re-upload, or a marketplace update the user triggers           | manual                                                                        |

**Load guarantee**: organization instructions always load. A skill loads only on
a description match. A docstring always arrives, but only at the moment the
model is already about to call that tool.

### Why organization instructions carry the trigger

This is the piece the original design was missing. Organization instructions sit
at Organization settings, Organization and access, are available to Team and
Enterprise plans, cap at 3,000 characters, and are included in every message for
every user across Chat, Cowork, and Code. They take up to an hour to propagate.

That is far too small to hold the protocol and exactly the right size to hold
the trigger. It converts a model-judged match into an instructed handoff, which
is the single largest reliability gain available anywhere in this design.

### Why the gate does not go in the `load` docstring

An earlier version of this design put the calibration gate in the `load` tool's
docstring, reasoning that `load` is a chokepoint because no Cube number can be
produced without it. That reasoning is circular and the idea is dropped.

The gate's content is "call `load` with an attendance query before answering."
But the calibration call and the answer call are the same tool, and the
docstring arrives at schema-read time, which is the moment the model has already
decided to call `load`. A docstring cannot distinguish the gate call from the
answer call. `stateless_http=True` is required for multi-instance Cloud Run, so
there is no session state to enforce against either.

`load` keeps exactly one sentence, a pointer rather than a procedure:

> Session protocol governs this tool. If it has not loaded in this conversation,
> load it before answering.

A pointer survives staleness in a way a procedure does not, and it keeps the
procedure in one place.

### Skill decomposition: split by cadence, never by protocol versus conventions

One protocol skill, then one skill per domain:

```text
cube-data-session              protocol, domain-agnostic, target ~600 words
assessment-cube-conventions    instrument families, target ~250 words
grades-cube-conventions        later
operations-cube-conventions    later
```

Each domain skill's **first line is a step, not a cross-reference**:

> If `cube-data-session` has not run in this conversation, load and run it
> before answering, then return here.

That keeps the gate procedure in one file forever. Adding a domain creates one
skill and edits zero lines of `cube-data-session`.

Peer skills split along protocol-versus-conventions were rejected: two
independent match events with no platform-enforced ordering, whose failure mode
is silent, because domain conventions get applied without the protocol gate ever
running.

Two constraints bound this. A skill `description` caps at 1,024 characters and
must be written in the third person. Recall degrades as skill metadata competes
for attention in the system prompt, and Anthropic names trigger competition as
the scaling limit, with no built-in evaluation runner. Both argue for sharp,
keyword-dense domain descriptions rather than broad ones.

**Broad descriptions are rejected on local precedent.**
`dbt:answering-natural-language-questions-with-dbt` ships with exactly the
breadth an earlier version of this design proposed, and the root `CLAUDE.md`
already carries a permanent countermand telling Claude to ignore it when it
auto-loads. Shipping a second broad data-question description repeats a cost
this repo has already paid.

## Content placement rule

This supersedes the earlier "move as much as possible to YAML first" rule. Apply
in order and stop at the first match.

1. **Judgment, order of operations, session record, PII gate, deliverable
   rules** go to the skill.
2. **Unratified convention** goes to the skill, never to YAML.
3. **Single-field meaning, null and coverage behavior** go to that member's
   `description`, capped at about 400 characters, with no dated numbers, no
   tables, and no inventories.
4. **Cross-field caution every consumer needs** goes to the view `description`.
5. **Query-construction mechanics that apply to any subject** go to the MCP tool
   docstring.
6. **Dated empirical inventories** go to a bundled reference file carrying an
   "as of" date, and never into `meta`.

Rule 1 sits ahead of rule 4 deliberately. The calibration-artifact instruction —
label the difference as a gap between instruments, flag it for team review, and
do not present it as a finding — literally satisfies the cross-field-caution
test in rule 4. Without the reordering it would land in a Tableau field tooltip.

Rule 6 exists because the residue does not fit anywhere else. About 47 percent
of the reference file's Shared conventions section resists rules 1 through 5,
and the residue shares one shape: dated empirical inventories. Band-set tables,
module-type volumes, coverage matrices, deduplication rates, median test dates.
None are field semantics, and putting them in a description turns them into
uncorrectable stale numbers in every consumer's field picker.

### Why the wholesale move to YAML was dropped

Three findings, each sufficient on its own.

**The channel is full.** The payload is already over the tool-result budget and
growing without help. Draining half the reference file into member descriptions
takes the assessment chain past 30,000 description characters and the total past
about 180,000 bytes, on a channel every session pays for unconditionally.

**The audience does not exist yet.** The justification was that YAML reaches
every consumer while a skill reaches only Claude. Tableau reads BigQuery marts
directly through 260 `rpt_tableau__*` models. Superset user impersonation is a
follow-up integration in this repo's own docs. Whether Cube's SQL API exposes
member `description` to a Postgres client is unverified. Today the only live
reader of a Cube member description is the same model that would read a skill.

**The volatility argument ran backwards.** "Volatile content cannot go in YAML
because it needs a redeploy" is wrong on the measured propagation table above:
YAML is the _fastest_ channel here, and the skill is the slowest. Rule 2
survives, but on a different justification — an unratified convention should not
appear as settled fact in a field tooltip a BI user reads without context.

### A rule this repo already overrode

The prior guidance said "single source; the skill points, it does not restate."
`src/cube/mcp/eval/arms.py` shows the team held dimension descriptions constant
and varied the docstring, then shipped the academic-year crosswalk in **both**
the `load` docstring and `dates.academic_year_label.description`. Duplication
measured better for the most-tested convention in the codebase. The rule needs
revisiting on evidence rather than inheriting.

## Covered-domain behavior: disclosure, never refusal

Cube scopes student data by location and entity only. All three student views
use `member_level: { includes: "*" }`, with `row_level` filters for
`student-region`, `student-school`, and `student-network`. There is no
domain-level restriction, and there should not be: a compensation researcher
legitimately needs every dataset, and the incumbent business-intelligence tools
do not gate by domain either. A governed path that refuses a question Tableau
would answer is worse than the ungoverned one, and people route around it.

So the covered-domain list drives the **confidence** layer, not access:

- Nothing is refused. Every view stays queryable by anyone Cube admits.
- A question touching a domain with no ratified conventions is answered, labeled
  exploratory with no vetted guidance, and names who owns ratifying it.
- It is recorded in the session record's existing `Out-of-scope` field.

That field already exists in the record template, so this points existing
machinery at a new input rather than building anything. It also yields a
measured count of how often people ask about uncovered domains, which is the
roadmap priority order.

## Delivery

`teamster` authors. A separate private repository publishes as the plugin
marketplace, because **organization marketplaces do not accept public
repositories**, and `teamster` is public. The user-added marketplace path does
accept public repositories, but it loses required-install and group scoping,
which are the reasons for choosing a plugin.

A plugin rather than bare provisioned skills, for three reasons:

1. A provisioned bare skill can be toggled off by the user. Only a **Required**
   plugin cannot be removed.
2. Bare skills go to everyone with no scoping. Scoping a skill to a team
   requires wrapping it in a plugin.
3. A plugin can carry the Cube connector, so a new cohort member installs once
   instead of adding a connector URL and completing an authorization flow
   separately.

Plugins do reach claude.ai chat on the web and the Desktop Chat tab, as well as
Cowork. One Anthropic documentation surface states the opposite and is stale.
Hooks and subagents are inert in Chat but live in Cowork and Claude Code, so a
hook can enforce the gate deterministically for the data team in Claude Code
even though it cannot for chat users.

Group preferences resolve to **most permissive** across multiple group
memberships, so a group-level "Not available" is defeated by any other group.
Set the organization-wide preference to `Not available` and grant per group.

Squash merge to `main` is the release. No administrator approval per release:
the existing pull-request review is the gate, and adding an admin step means
guidance improvements queue behind an inbox, which is how these files went stale
before.

### Two live formats during the transition

Assessment graduates to the skill. Grades, GPA, and later domains pilot in the
current Project format, in parallel rather than daisy-chained.

The load-bearing rule is one line: **a domain lives in exactly one target at a
time.** Assessment goes to the skill. Grades stays in a Project. Never both,
because two live copies of one domain's conventions with different update paths
is the actual collision risk.

Mechanics:

- Skill-shaped source is authoritative. Project artifacts are **generated**,
  including the custom-instructions block, which is the piece most likely to
  drift because it is pasted by hand today.
- Generated artifacts are never hand-edited.
- Graduation is atomic: a domain's Project source files are deleted in the same
  pull request that adds the domain to the skill.

Apply the `skills-lock.json` `computedHash` pattern to generated artifacts
immediately rather than deferring continuous integration: commit a hash of the
rendered output beside the source, and add one step that re-runs the generator
and diffs. That removes the "continuous integration when the second domain
lands" trigger, which had no owner watching for it. `.github/CLAUDE.md` already
records a markdown-excluded deploy path firing anyway, so path filtering should
not be trusted on the first build.

The three existing pilot users are **migrated, not frozen**. Freezing orphans
them silently: once the Project source files are deleted no pull request can
reach them, the live Project simply stops receiving corrections, and the next
ratified decision reaches everyone except the three people who piloted it.

## Version stamping

Two stamps, because two things go stale invisibly.

A version line in `SKILL.md`, echoed into the session record header. A claude.ai
session has no repository access, so this is the only way a record states which
guidance produced it.

A connector guidance version in the **`load` response payload**, not in `meta`.
A stamp in `meta` reports the _deployed_ version while the model obeys the
_connect-time-cached_ docstring, so it would read the current version while
running an older one — an assurance signal that is wrong precisely when it
matters. The `load` response is generated per request and cannot be stale.
Derive it from the deploy, never from a hand-maintained constant, because a
stamp someone forgets to bump is worse than no stamp.

Neither stamp fixes anything. They only make staleness visible, and the fix
stays a manual reconnect.

## Review gate

`claude-code-review.yaml` triggers on `src/`, `tests/`, `scripts/`, and
`.github/workflows/`, and this repo's convention is `!**/*.md` negation rather
than `paths-ignore`. So guidance markdown receives no automated review wherever
it lands.

`.claude/` belongs to `@TEAMSchools/platform`; `src/cube/` belongs to
`@TEAMSchools/analytics-engineers`. Analytics engineers can catch "this
contradicts the data." They are not tasked with catching "this states an
unratified convention as settled." So CODEOWNERS names an individual with
instructional-domain competence for the plugin path, and
`.github/pull_request_template.md` gains a "Skill and guidance content" section.

## Out of scope

- The wholesale move of `assessment-cube-reference.md` into Cube YAML. See the
  reasoning above.
- Grades, GPA, and operations domains. They stay in the current Project format.
- The reference file's open-decisions list. Those route to instructional
  leadership, not engineering.
- Small-cell suppression. Deliberately removed from all guidance at the user's
  direction, tracked separately in
  [#4237](https://github.com/TEAMSchools/teamster/issues/4237).
- Standards-code fragmentation, filed as
  [#5349](https://github.com/TEAMSchools/teamster/issues/5349). Upstream dbt
  data, independent of this work.

## Open questions

These are in-product checks, not research questions. None blocks the first
release.

1. Whether a plugin-bundled connector collides with a manually added one.
   Undocumented. The first new install answers it, which is why the three pilot
   users migrate after a new cohort member installs, not before.
2. Whether component-level disable is suppressed inside a `Required` plugin.
   Undocumented. One test install answers it, and it decides whether the
   guidance is enforceable or advisory.
3. Whether `pct_proficient_formative` should cover three module types or seven.
   **Not a defect.** Its filter is `module_type IN ('QA', 'MQQ', 'CRQ')`, and
   whether TP, UA, ET, and WPP are formative is an unratified definition that
   got answered in YAML rather than routed to instructional leadership. The only
   false thing in the description is the word "all". This is a Topline
   definitional question, and the two readings produce different numbers for the
   same named metric: about 800,000 scores, roughly a third of module-coded
   work, are excluded today.

## Schedule honesty

The roadmap goal is every key domain modeled by the end of school year 2027,
with skills as the delivery layer. The arithmetic does not support that as a
commitment.

Assessment is the best case: Cube views already built, an enthusiastic
three-person pilot, one person driving. It still took about ten recorded
sessions and four rounds of documentation pull requests to reach maturity.
Grades and GPA are comparable. Operations is very likely larger, because it
probably needs new dbt marts and new Cube modeling rather than guidance
iteration alone. The functional memos imply several more domains that are
neither scoped nor staffed.

Five or six remaining domains, roughly nine to ten months of runway, one person
driving, and the parallel tracks in this design are parallel _targets_, not
parallel _people_. Treat the date as a stretch goal. Either cut the domain
count, lower the maturity bar below assessment's, or add people.
