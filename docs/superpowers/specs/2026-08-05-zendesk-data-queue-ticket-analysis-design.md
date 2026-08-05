# Zendesk Data-queue ticket and response analysis

Design spec for [#4739](https://github.com/TEAMSchools/teamster/issues/4739).

## Goal

Partition the Data team's Zendesk queue into tickets that should never have
existed and tickets that represent genuine demand. For the genuine remainder,
identify the recurring request types and the recurring responses behind them,
and recommend — per cluster, on evidence — whether the right intervention is an
automated reply, an agent macro, an AI-drafted suggestion, a link to an existing
Help Center article, a change to intake, or nothing at all.

The partition comes first and it is load-bearing. This team owns the platform
the tickets are about, so a request caused by its own design decision is a
defect, not demand — and templating a defect's reply lowers the cost of the
symptom until nobody funds the cure. See
[Phase 0](#phase-0--the-self-inflicted-partition-gate).

Phase 1 is analysis. It produces a report, a platform defect backlog, and draft
reply templates. It does not ship anything into Zendesk and adds no models to
the warehouse.

## Scope

| Dimension  | Value                                                                                   |
| ---------- | --------------------------------------------------------------------------------------- |
| Groups     | `Data` (id 21474460, 3,790 tickets), `Teaching and Learning` (id 31319068, 818 tickets) |
| Date range | `created_at` 2024-07-01 through 2026-06-30                                              |
| Tickets    | 4,608                                                                                   |

Two complete school years, SY24-25 and SY25-26. SY26-27 is excluded — it is
three weeks old and would distort year-over-year comparison.

`Teaching and Learning` is included because 218 of its tickets carry a `data*`
category, so the Data team is evidently answering some of them. It also runs its
own `teaching___learning__*` category family, most of which appears only in
SY25-26. If the report shows T&L behaves as a distinct queue with distinct
responses, it gets split out rather than averaged in.

## Corpus profile

Established during design, from BigQuery:

| Signal                                      | Count |
| ------------------------------------------- | ----- |
| Tickets in scope                            | 4,608 |
| Have audit rows (thread retrievable)        | 4,476 |
| Have at least one public comment            | 4,474 |
| Have an agent public reply (2 or more)      | 4,130 |
| Single-exchange (exactly 2 public comments) | 1,341 |
| No public agent reply (exactly 1)           | 344   |
| Had a macro applied                         | 834   |
| Reply contains a Help Center article link   | 216   |
| Article link in the first agent reply       | 149   |
| Distinct articles ever linked               | 62    |

Mean public comments per ticket is 3.69. First agent replies are short — 336 to
483 characters depending on thread length.

Category distribution within scope, categories at 15 tickets or more. 63
distinct categories appear; the 43 below the cutoff hold 90 tickets between
them.

| Category                                 | SY24-25 | SY25-26 | Total |
| ---------------------------------------- | ------- | ------- | ----- |
| `data__deanslist`                        | 459     | 471     | 930   |
| `data_power_school`                      | 317     | 309     | 626   |
| no category                              | 261     | 320     | 581   |
| `data_blended_learning`                  | 378     | 113     | 491   |
| `data__perf_mgmt___surveys`              | 212     | 190     | 402   |
| `data_data_analysis_and_reports`         | 208     | 176     | 384   |
| `data__grow`                             | 167     | 52      | 219   |
| `teaching___learning__amplify`           | 0       | 144     | 144   |
| `teaching___learning__iready`            | 27      | 79      | 106   |
| `teaching___learning__illuminate`        | 47      | 47      | 94    |
| `teaching___learning__other`             | 66      | 27      | 93    |
| `data__custom_app`                       | 73      | 17      | 90    |
| `data_illuminate`                        | 45      | 34      | 79    |
| `data__staff_info`                       | 49      | 22      | 71    |
| `data__dibels`                           | 50      | 13      | 63    |
| `data_compliance_reporting`              | 31      | 23      | 54    |
| `data_other`                             | 19      | 16      | 35    |
| `teaching___learning__clever`            | 0       | 23      | 23    |
| `teaching___learning__google_classroom`  | 0       | 17      | 17    |
| `teaching___learning__backlog_close_out` | 13      | 3       | 16    |

Composition of the 4,608: 3,465 carry a `data*` category, 562 carry a
non-`data*` category (nearly all `teaching___learning__*`), and 581 carry none —
479 in `Data`, 102 in `Teaching and Learning`.

Two patterns here undercut naive year-over-year comparison, and the report must
handle both rather than pooling the years:

- **Five `data*` categories more than halved.** `data_blended_learning` 378 to
  113, `data__grow` 167 to 52, `data__custom_app` 73 to 17, `data__dibels` 50 to
  13, `data__staff_info` 49 to 22. Real demand decline, a tooling change, or
  recategorization drift — unresolved.
- **T&L categorization was largely introduced in SY25-26.**
  `teaching___learning__amplify` goes 0 to 144, `clever` 0 to 23,
  `google_classroom` 0 to 17, `iready` 27 to 79. These are almost certainly
  labeling-practice changes rather than demand changes, so their trend lines
  mean something different from the `data*` ones.

Uncategorized tickets also rose, 261 to 320, which argues against reading any
category trend as clean demand signal.

## Data sources

Two sources, split by job. Neither is a substitute for the other.

### BigQuery, for the corpus scan

`kipptaf_zendesk.tickets` and `kipptaf_zendesk.ticket_audits`, both
Airbyte-synced. Reply bodies live in the `ticket_audits.events` JSON array, per
event: `type`, `public`, `author_id`, `body`, `html_body`, `plain_body`.

`stg_zendesk__ticket_audits__events` extracts only `type`, `field_name`,
`value`, and `previous_value` — no body text. `fct_support_tickets` carries no
body text either. The analysis therefore reads the raw source tables directly.
Surfacing bodies in a staging model is deliberately out of scope; see
[Out of scope](#out-of-scope).

Fidelity was verified on ticket 469873: a 4,464-character description returned
whole with an intact tail, and all six comment bodies present at full length,
matching the count the Zendesk API reports for that ticket.

One known ceiling: 5 of the 4,608 tickets have `description` capped at exactly
65,535 characters by the Airbyte sync. Read those five through the MCP.

`fct_support_tickets` is **not** a usable base for this work, despite being the
obvious candidate. It inner-joins submitters to `int_people__staff_roster`,
which drops roughly a third of tickets (63,670 rows against 95,564 raw for the
two years network-wide), and it carries no `group_id`, so it cannot express the
scope filter at all. Read the raw source tables.

### Zendesk MCP, for exemplar reads

`get_ticket_conversation` returns chronologically ordered entries with
agent-versus-requester side, resolved author names, public-versus-private
visibility, inline images rendered as placeholders, and an attachment list. The
raw audit JSON provides none of that cleanly, and template wording depends on
reading threads the way an agent sees them.

The MCP account is scoped to the `Data` group. It sees roughly 4 percent of the
whole Zendesk instance but effectively all of this scope, confirmed by
`get_ticket` succeeding on an in-scope ticket and by its search counts tracking
the BigQuery Data-group counts within a few percent.

### Help Center inventory

14 categories, 67 sections. Eight are relevant here: `Data | Launch`,
`Data | Dashboards`, `Data | DeansList`, `Data | PowerSchool`,
`Data | People Data`, `Illuminate + Assessments`, `Teaching and Learning`, and
`Focus | KIPP Miami SIS`.

## Normalization

This is the load-bearing step; every signal downstream depends on it.

Ticket 469873 is the cautionary case: its 4,464-character description is five
nested email forwards, and the actual request is the first ~500 characters.
Naive similarity on raw text would cluster that ticket with every other
forwarded thread rather than with other audit-request tickets.

Pipeline, applied to both request text and reply text:

1. Decode HTML entities. `plain_body` is not clean plain text — `&nbsp;` appears
   throughout.
1. Cut quoted-thread tails at `From:` / `Sent:` / `On ... wrote:` / long
   underscore rules. Keep the leading original content.
1. Strip email safety banners (external-sender warnings) and signature blocks
   (name, title, address, phone, scheduling links).
1. Substitute volatile and identifying tokens with placeholders: `{student}`,
   `{student_number}`, `{staff}`, `{school}`, `{date}`, `{term}`, `{ticket}`,
   `{url}`.
1. Lowercase and collapse whitespace.

Step 4 does double duty: it is what makes near-duplicate matching find replies
that differ only by which student they name, and it is what makes the resulting
templates safe to circulate.

Normalization is validated before use: hand-check 30 stratified samples against
their `get_ticket_conversation` output and confirm the retained text is the
actual request or reply. A silent over-strip would suppress real clusters, so
this check gates the rest of the work.

## Phase 0 — the self-inflicted partition (gate)

Runs before any reply clustering, and gates it.

The corpus splits two ways:

- **Self-inflicted** — a platform defect this team owns and could remove. An
  integration that silently drops records, a measure named to invite misreading,
  an access model that needs a human for every grant, a dashboard with no
  drill-through.
- **Genuine** — new questions, one-off analyses, vendor outages, school-side
  data entry. A real service-response problem, where macros and articles help.

Classifying a ticket as self-inflicted requires **all three** of the following.
Anything failing all three returns to the genuine pile, and the audit reports
its demotion rate so a reader can see how hard the rubric bit:

1. It resolved with no change outside the team's control.
1. The resolving action is one of re-run, backfill, grant, or explain.
1. At least N other tickets resolve the same way against the same named
   artifact. Recurrence is what turns an incident into a defect.

Two joins do most of the work without reading any text:

- Ticket `created_at` landing shortly after a failed or late Dagster
  materialization of an asset upstream of the artifact the ticket names. The
  requester is functioning as the alert nobody built.
- Any ticket resolved by a permission grant. Count distinct grantees per view —
  a view needing thirty manual grants is one config bug, not thirty requests.

The "this number looks wrong" genre splits by what happened next. A commit
touching the referenced dbt model within ~14 days means a real defect plus a
missing test. No code change plus a long explanatory reply means a naming or
semantics defect, owned by whoever named the measure.

Artifact names resolve against inventories the team already publishes — dbt
models and exposures, Cube `meta`, Tableau views, Dagster asset keys,
CODEOWNERS.

**Region as a natural control.** One platform, four populations. Normalize
tickets-per-artifact by active users per region and treat variance as the
discriminator: uniform load means platform defect, a single-region spike means
config, roster, or onboarding gap. This is the cheapest guard against the most
expensive mislabel — rebuilding a dashboard that is fine everywhere except the
one region that never got trained on it.

**Kill criterion, committed before labeling starts.** If the self-inflicted rate
in the uncategorized pool comes in under 20%, the thesis is wrong. Say so in the
report and let clustering proceed against the whole corpus unchanged.

## Signals across the genuine partition

Run over the tickets Phase 0 classifies as genuine — or over all 4,608 if Phase
0 hits its kill criterion. Their purpose is to decide what gets read, not to
produce the deliverable.

1. **Near-duplicate reply clusters.** MinHash over 5-gram shingles of the
   normalized first agent reply, Jaccard threshold 0.7, tuned against a
   hand-labeled sample. Replies agents already paste repeatedly are the
   highest-confidence templates that exist, and finding them needs no model.
1. **Macro usage.** Join the 834 `AgentMacroReference` events to category and
   cluster. Which macros exist, where they are applied, and where an agent
   applied one then rewrote it heavily — the rewrites indicate a macro that does
   not fit its use.
1. **Structure per category.** Turn count, first-reply length, time to first
   reply, single-exchange rate, and the 344 no-public-reply tickets. High
   single-exchange rate plus low reply variance is the auto-reply signature.
1. **Request-side sub-typing** within the six categories above 200 tickets, so
   DeansList's 930 split into actual request types rather than staying one
   label.
1. **Article-link analysis.** The 216 article-linking tickets, resolved to the
   62 distinct articles, cross-tabulated against cluster. Produces both the
   already-deflected set and the gap: recurring clusters with no article link
   where an article nonetheless exists.
1. **Uncategorized bucket.** The 581 category-less tickets — do they land in
   existing clusters, or is the taxonomy missing something?

## Reading and judgment

For every cluster clearing a floor of 15 tickets across two years — roughly one
a month, below which no automation repays its maintenance — read about 10
exemplars via `get_ticket_conversation` and record:

- what is being asked, in plain language
- what the standard response _does_: answers, asks a clarifying question, hands
  off, links an article, or delivers a data pull
- what varies between instances, which is what decides the mechanism
- whether resolution required information the requester should have supplied up
  front

That last point matters more than it looks. For a queue built on data requests,
tightening the intake form frequently beats automating any reply, because it
removes the clarifying round trip instead of scripting it.

## Mechanism assignment

Per cluster, on evidence, from six options. **Fix the platform is checked
first** — every other row presumes the ticket should exist:

| Mechanism        | Evidence required                                                                                         |
| ---------------- | --------------------------------------------------------------------------------------------------------- |
| Fix the platform | Phase 0 classified the cluster self-inflicted, with a named artifact and a buildable fix                  |
| Link an article  | A published article already answers it; agents link it inconsistently or not at all                       |
| True auto-reply  | Response is invariant after placeholder substitution, needs no judgment, and single-exchange rate is high |
| Agent macro      | Response is stable in shape but an agent must fill or verify something                                    |
| AI-drafted       | Intent is consistent, wording and specifics vary too much for fixed text                                  |
| Do not automate  | Low volume, high variance, or consequential enough that a wrong send costs more than the time saved       |

Every recommendation carries its supporting numbers — cluster size, variance
measure, single-exchange rate — so the call is auditable rather than asserted.

Self-inflicted clusters are additionally priced in annual hours: agent handle
time (comment count times median minutes) plus requester wait time. Platform
defects lose prioritization fights because their cost is diffuse and lands on
other people's calendars, mostly teachers' and school leaders'. A number is
usually the difference between a defect that gets discussed and one that gets
scheduled.

## Named question: did the DeansList articles move volume?

The `Data | DeansList` Help Center category and its eight sections were created
2025-07-22 and 2025-07-23 — between the two school years in scope. DeansList
ticket volume within scope went 459 in SY24-25 to 471 in SY25-26. Flat, across a
substantial article build-out.

This is a natural experiment already sitting in the data, and it bears directly
on the premise of the whole project. Candidate explanations to test:

- the articles address different questions than the tickets actually ask
- the articles exist but are not discoverable, and agents do not link them
- ticket volume is driven by requests articles cannot satisfy (data pulls,
  permission grants, corrections to records)
- **documenting a defect does not reduce demand for the defect** — the article
  explains a workaround for something that should have been fixed
- volume would have grown without them, so flat is a win

Method: sub-type the DeansList tickets, compare sub-type mix across the two
years, and cross-reference each sub-type against the article set published in
July 2025. A shift in mix under flat totals means something different from no
shift at all.

The fourth explanation gets its own cheap test — **read the Help Center as an
inverted defect log**. Score every Data-relevant article as defect-documenting
(it exists to explain a confusing metric name, document a workaround, or
reconcile why this number differs from PowerSchool) versus genuinely
instructional. The defect-documenting ones are bug reports with good SEO, and
they route straight into the Phase 0 backlog. This needs no ticket-text
extraction at all — the articles are already written, and whoever wrote them
already prioritized them.

Answering this honestly may weaken the case for reply automation. That is the
point of asking it first.

## Opening week

Three probes, each half a day to a day, each with a kill criterion committed
before it runs. None requires a branch, a model, or a code change. Their results
decide whether the rest of this spec runs as written.

1. **Partition probe.** Pull the 581 uncategorized tickets plus every ticket
   whose first agent reply matches an access or grant lexicon. Stratified-sample
   ~150 across both school years and all four regions. Hand-label three ways —
   self-inflicted, genuine, vendor-or-user-error — where choosing self-inflicted
   requires two mandatory fields: the artifact name and a one-sentence fix.
   Output: a base rate plus roughly ten candidate artifacts. **Kill at under 20%
   self-inflicted.**
1. **Reply-shape probe.** Read the first agent reply on ~200 recently solved
   tickets in `data_data_analysis_and_reports` and `data_blended_learning`. Code
   each as pasted value, attached file, link to an existing object, or not a
   data ask, plus a free-text question-shape slug. Output: what share of volume
   is even number-shaped, and how many slugs recur. **Kill if fewer than ~20
   slugs cover half the number-shaped volume** — that is a long tail, and a
   re-runnable-object policy would be a tax rather than a saving.
1. **Seasonality probe.** Count tickets by category and
   week-offset-from-first-instructional-day per academic year. For the top five
   cells consistent across both years, hand-tag whether the tickets inside are
   the same ask or merely the same week. Output: whether seasonal pre-building
   has a target at all. **Kill if no cell holds 10 or more same-ask tickets in
   both years.**

Week-offset, not calendar week: school calendars diverge across the four
regions, particularly at year-end, so calendar-week grouping smears the very
spikes it is meant to find.

The seasonality probe has a fallback worth more than its parent. Even if no cell
supports pre-building, multiplying forecast volume by median resolve time per
category yields a load calendar the team can schedule its own project work,
deploy freezes, and coverage around — all of the forecast's value, none of the
speculative build.

## Deliverables

1. **Platform defect backlog** — one row per artifact: ticket count, estimated
   annual hours, named owner from dbt meta / CODEOWNERS / Dagster code location,
   and a one-line fix. Any artifact with no nameable fix is demoted back to
   genuine, and the demotion rate is reported.
1. **Ticket-type map** — categories to sub-types, with volumes, year-over-year
   trend, and single-exchange rate.
1. **Response-pattern catalog** — clusters with size, representative normalized
   text, and variance notes.
1. **Draft reply templates** — placeholder-parameterized, one per cluster that
   warrants one.
1. **Mechanism recommendation per cluster** — from the five above, with the
   numbers that support it.
1. **Article-coverage gap analysis** — recurring clusters with an existing
   unlinked article, and clusters with no article at all.
1. **DeansList before-and-after finding** — the named question above, answered.
1. **Byproducts** — intake-form gaps, disposition of the 581 uncategorized
   tickets, taxonomy collapse candidates among the categories under 100, and the
   three categories that dropped by more than half.

Working report with real examples in `.claude/scratch/`. A scrubbed version is
what leaves the machine.

## Out of scope

- No dbt models and no warehouse writes. Surfacing reply bodies in
  `stg_zendesk__ticket_comments` is the natural follow-on once the analysis
  shows what is worth maintaining, not a prerequisite.
- No embedding-based clustering unless the near-duplicate pass leaves more than
  half the corpus unexplained. At 4,608 tickets the reusable replies are likely
  already near-identical copy-paste, which is a text-normalization problem
  rather than a clustering one. Reserved, not rejected.
- No changes to Zendesk macros, triggers, forms, or Help Center articles.
- Phase 0 **produces** the defect backlog; it does not work it. Fixing the
  artifacts is separate, scheduled engineering with its own prioritization.
- No other function's queue. Technology (21,179 tickets), Accounts Payable
  (20,206), Facilities (18,086), and HR (16,114) are deliberately excluded.

## PII handling

Data-queue ticket bodies concern student records — DeansList, PowerSchool,
Illuminate — and contain student names, student numbers, and staff identifiers
throughout. Under the repo convention and FERPA's direct-identifier list, all of
it stays local.

- Real examples live only in `.claude/scratch/` and the terminal.
- Placeholder substitution during normalization is the primary scrubbing
  mechanism; templates are built from normalized text, not raw text.
- Before anything reaches GitHub, Asana, Slack, or a shared document,
  identifiers are replaced with labels (`Student A`, `a school leader`) or
  referred to by column name.
- Aggregates and counts are not PII and may be shared freely.

## Assumptions to validate

- **Comment sequence 1 is the requester.** The single-exchange and first-reply
  metrics assume the first public comment is the ticket description and the
  second is the first agent response. Agent-created tickets would break this.
  Verify by comparing `author_id` on comment 1 against `requester_id` before
  relying on any first-reply metric.
- **`AgentMacroReference` implies the macro's text was sent.** An agent can
  apply a macro and then delete its content. Spot-check before treating macro
  application as evidence of a reused reply.
- **Group membership is a stable proxy for queue ownership.** Tickets reassigned
  across groups mid-life are attributed to their final group; if reassignment is
  common, the scope boundary is softer than it looks.

## Risks

- **"Self-inflicted" is a counterfactual, and therefore elastic.** With enough
  motivation any ticket becomes a platform defect — "we should have built a
  clearer dashboard" — and the bucket inflates into a several-hundred-item
  backlog nobody works, read by the team as blame rather than diagnosis.
  Contained by the three-part rubric, the mandatory artifact-plus-fix fields,
  and publishing the demotion rate.
- **Reply text describes the fix, not the cause.** "Reran the sync" is written
  identically for the team's own orchestration bug and for a vendor's malformed
  file drop, so verb-based classification systematically over-attributes
  external failures to the team. Every self-inflicted label needs a named
  artifact the team actually owns, not just a matching verb.
- **Normalization over-strips and suppresses real clusters.** Mitigated by the
  30-sample validation gate, which blocks the rest of the work until it passes.
- **The two years are not comparable.** Five `data*` categories more than
  halved, the T&L category family was largely introduced in SY25-26,
  uncategorized volume rose, and a Help Center build-out landed between them.
  Report per-year figures alongside totals rather than pooling by default, and
  treat any category whose labeling practice changed as unusable for trend.
- **Volume does not equal cost.** A 951-ticket cluster of 30-second replies may
  matter less than a 40-ticket cluster that eats an afternoon each.
  Time-to-resolve is captured alongside volume so the recommendation is not
  purely a headcount.
- **Analysis outruns appetite.** The report recommends; adoption is a separate
  decision. Nothing here commits the team to building anything.
