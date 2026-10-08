# Zendesk ticket to Claude skill router — design

Refs [#5803](https://github.com/TEAMSchools/teamster/issues/5803). Builds on the
ticket skill ([#5630](https://github.com/TEAMSchools/teamster/issues/5630)) and
the August intern scoping findings
([#4862](https://github.com/TEAMSchools/teamster/issues/4862)).

## Problem

The data team solves some Zendesk tickets end to end with Claude Code skills.
`gradebook-audit` and `dibels-dashboard` are the clearest cases. A person picks
each ticket by hand, and about 10 have been solved this way. We want a system
that reads a new ticket in the Data or Teaching & Learning groups and names the
skill, if any, that applies, so the agent who picks it up starts with the right
tool.

The missing input is a labeled set, not a model. Zendesk has no field that says
which skill could have solved a ticket. The `Category` custom field looks like a
label, but the agent sets it after triage, so it is unavailable at intake and it
encodes the agent's habit rather than the ticket. The 10 tickets Claude has
solved are far too few to train on and were hand-picked to be obviously
skill-shaped, so they are a sanity check, not a training set.

What the warehouse does have is the human resolution. The raw
`kipptaf_zendesk.ticket_audits.events` JSON carries every comment body: 512k
public comments across 173k tickets and 50k internal notes. The dbt staging
model `stg_zendesk__ticket_audits__events` drops the body, which is why the
ticket skill's reference says the warehouse has no comments. The labeling pass
reads the raw table.

### Scope and size

Data and Teaching & Learning groups, tickets created on or after 2024-07-01.

| Group               | Created | Solved or closed | Created since 2025-07-01 |
| ------------------- | ------: | ---------------: | -----------------------: |
| Data                |   4,319 |            4,028 |                    2,390 |
| Teaching & Learning |   1,164 |            1,026 |                      842 |
| Total               |   5,483 |            5,054 |                    3,232 |

Solved volume grows about 300 a month. Top solved categories: DeansList 1,089,
PowerSchool 742, Data analysis and reports 524, Perf mgmt and surveys 412,
Blended learning 488 across both groups, Amplify 195, iReady 161, DIBELS 62.
About 130 are uncategorized and about 60 carry another department's category.
Both stay in the set; the labeler reads the thread, not the category.

Of the roughly 60 local skills, about 12 are ticket-shaped: `gradebook-audit`,
`dibels-dashboard`, `graduation-pathways`, `grad-plan-tracking`,
`hs-early-warning`, `collegeboard-id-crosswalk`, `carat-dashboard`, `stat-dash`,
`fresh-dashboard`, `athletic-eligibility`, `crdc`, `focus-sis-district-reports`,
and `zendesk-help-articles`. DeansList, i-Ready, Perf mgmt and surveys, and
Blended learning have no skill.

## Approach

3 shapes were considered for the router.

- **A — zero-shot LLM classifier.** The skill descriptions are the label
  definitions. No training. Improves whenever a description is edited. Needs a
  labeled set only to measure, not to build.
- **B — classic supervised model.** BQML boosted tree over intake text, or
  `ML.GENERATE_EMBEDDING` plus nearest neighbour over solved tickets. Needs
  labels to build. After labeling, most skill classes will have tens of
  examples, which is too thin to trust a multi-class model.
- **C — retrieval only.** Show the agent the 5 most similar solved tickets and
  let them infer the skill. This is what `research()` in the ticket skill
  already approximates through Zendesk search.

**Selected: A, measured against a human gold set, with B held as a fallback once
the feedback loop has produced human-confirmed labels.**

Two adversarial reviews on 2026-10-08 changed 4 things from the first draft.
Each is recorded in its section below: the labeler records facts rather than a
skill name; the evaluation gets an intake-only run and a human gold set; the
DeansList and i-Ready skill decisions come after labeling rather than before;
and v1 is a suggestion in the queue rather than an automated agent run.

## Sequence

Each step gates the next.

### 0. Legal

Ask legal whether the Console API key falls under the same agreement as the
Claude Code seats, and whether those terms satisfy the FERPA school-official
conditions in §99.31(a)(1). Thread text already reaches Anthropic whenever
someone runs `research()` in the ticket skill, so the question is whether a
Console key is covered the same way. The message lists all 3 flows: the batch
labeling pass, a per-ticket router call at intake, and an agent run. For each,
it names the content sent (public comments, internal notes, the roster join) and
the retention. Batch results persist on Anthropic's side for 29 days unless
deleted, and the plan deletes each batch after download.

The fallback if the answer is no is BigQuery `AI.GENERATE` on Vertex, which
keeps the threads in-warehouse. The same prompt and schema work there.

SQL and stub-description work proceed while this is pending. Nothing sends a
thread until it is answered.

### 1. Labeling input

One BigQuery table, materialized once, in a restricted dataset with a table
expiration and `contains_pii` tags. One row per solved ticket in scope.

Intake fields come from the ticket's `Create` audit event, not the current
`tickets` snapshot. Agents edit subject and form after triage, so the snapshot
leaks post-triage information. Agent-created tickets (submitter differs from
requester) have agent-written descriptions and form their own stratum.

The thread comes from the raw audit JSON, ordered by time, each comment prefixed
`[public]` or `[internal]`. Internal notes are included in v1 and dropped if the
intake-only run (step 3) shows they do not change labels.

Redaction in SQL before anything leaves the warehouse: email addresses, phone
numbers, and digit runs of 6 or more characters.

Excluded before labeling, because each produces a fake `none`:

- tickets closed by the `Data - Close Out Older Ticket` macro
- merged and duplicate tickets
- tickets with no public comment from an agent

```sql
with comments as (
  select
    ta.ticket_id,
    ta.created_at,
    json_value(e, '$.public') = 'true' as is_public,
    json_value(e, '$.body') as body,
  from `teamster-332318`.kipptaf_zendesk.ticket_audits as ta
  cross join unnest(json_extract_array(ta.events)) as e
  where json_value(e, '$.type') = 'Comment'
),
threads as (
  select
    ticket_id,
    string_agg(
      concat(if(is_public, '[public] ', '[internal] '), body), '\n---\n'
      order by created_at
    ) as thread,
  from comments
  group by ticket_id
)
select t.id as ticket_id, t.subject, t.description, f.category, th.thread,
from `teamster-332318`.kipptaf_zendesk.tickets as t
inner join `teamster-332318`.kipptaf_marts.fct_support_tickets as f
  on f.url = concat('https://teamschools.zendesk.com/agent/tickets/', t.id)
inner join threads as th on t.id = th.ticket_id
```

The query above is the shape. The real one reads intake fields from the `Create`
audit event, applies the exclusions, and applies the redaction.

### 2. Stub descriptions

Before labeling, write 3-line stub descriptions for the narrow DeansList and
i-Ready cases a skill could plausibly solve: a DeansList sync or data diagnosis,
and an i-Ready roster or score-feed problem. These go into the label set beside
the 12 existing skills. The scoping findings say most DeansList volume is access
grants, picklist config, and guide deflection, and the repo's DeansList client
is GET-only, so a skill cannot perform the main action. The stubs let the
labeling pass answer whether the skill-shaped remainder is big enough to build
for.

### 3. Labeling batch

One Batch API job on `claude-opus-5-5` at effort `low`. The system prompt holds
every skill description verbatim (frontmatter `description` fields plus the
stubs) and is cached across requests. Each request carries one ticket,
`custom_id` is the ticket id, and the output is JSON-schema constrained.

The labeler records skill-independent facts, not a skill name. Skill
descriptions overlap (`graduation-pathways` and `hs-early-warning` both claim
`rpt_tableau__graduation_requirements`; `stat-dash` and `graduation-pathways`
both claim `int_assessments__state_nj_scores`), a single-label enum forces
arbitrary picks, and a label tied to a description goes stale when the
description is edited. Recording facts means adding a skill later is a
re-mapping query, not a relabel.

Schema:

| Field                 | Type                                                                                                               |
| --------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `system`              | enum: PowerSchool, DeansList, Amplify, iReady, Illuminate, Tableau dashboard, Google Sheet, Focus, other           |
| `dashboard_or_report` | short string, name only                                                                                            |
| `problem_type`        | enum: wrong value, missing data, access, config, how-to, request for analysis, incident, other                     |
| `resolution_path`     | enum: executed fix, explanation, redirected to school ops, self-serve, clarification needed, vendor, none          |
| `resolution_action`   | enum: warehouse or model fix, config-sheet edit, source-system edit by requester, access grant, code change, no-op |
| `resolution_observed` | enum: yes, partial, no                                                                                             |
| `candidate_skills`    | array of skill names, may be empty                                                                                 |
| `confidence`          | enum: high, medium, low                                                                                            |

No free-text summary field. The first draft had a `resolution_summary`, which is
tier-2 PII under `.claude/rules/ferpa-pii.md` and would have created a new
durable PII table. `reason` is dropped for the same reason.

The same batch includes a second request per ticket that sees intake fields
only, with the same schema. The gap between the two runs measures whether the
resolution label is predictable from the opening request. If intake-only
agreement with the gold set falls below about 70 percent, the router predicts
only `system` and `problem_type` at intake and the skill decision moves to the
agent.

Store each description's hash beside every label. Load results to
`<restricted dataset>.zendesk_ticket_labels` keyed on `ticket_id`, `run_kind`
(full or intake), and `model_version`. Delete the batch after download.

Cost: about 5,000 tickets, about 2,000 tokens each, about 10M input tokens,
about $20 at batch pricing plus 10 percent for the intake-only run.

Sanity check: run the full labeler on the 10 Claude-solved tickets with the
resolution hidden. If it misses several, the skill descriptions are the thing to
fix first.

Skill applicability is a rule over the facts: `system` and `problem_type` in the
skill's domain, and `resolution_action` in the set that skill can perform. The
rule lives in a small YAML next to the labeling script so a change is a diff,
not a prompt edit.

### 4. Gold set

Labels from the batch find candidates and build strata. They are never ground
truth. The first-draft evaluation compared a Claude router against Claude labels
made from the same descriptions, which measures self-agreement, not usefulness.

- 2 raters label 50 tickets blind to the model's output. Their agreement sets
  the ceiling on label quality.
- About 30 tickets per skill for the 2 or 3 skills with the most candidates,
  rated blind.
- A near-miss `none` stratum: tickets labeled with no skill that look most like
  a skill's positives, to estimate false negatives.
- The most recent 3 months are a holdout nobody tunes a prompt against.
- Rating happens in the BigQuery console or the terminal, not a Sheet. A Sheet
  of 200 ticket threads is a new PII surface.

A 200-ticket check across 14 strata is about 14 per class, and 16 of 20 correct
gives a 95 percent interval of roughly 58 to 92 percent, which cannot set a
threshold. Hence 30 per skill and only 2 or 3 skills in v1.

### 5. Skill decisions

From the per-skill counts: which existing skills carry enough volume to route (a
guess from the categories is `gradebook-audit` and `dibels-dashboard`), and
whether the DeansList and i-Ready stubs got enough high-confidence candidates to
be worth building. A relabel after a new skill exists costs about $20. A skill
nobody needs costs weeks. Record each decision in this spec.

### 6. Offline replay

Before any router runs on live tickets, replay each v1 skill on about 15
historical tickets with the resolution hidden. The resolver grades each draft as
usable, needs edits, or wrong, and records minutes the draft would have saved.
"Draft used with minor edits" is the success measure for the whole project.
Router precision is an input to it, not a substitute.

### 7. Router v1

A zero-shot call per new ticket with the same label definitions and schema, over
intake fields only. Output lands in
`<restricted dataset>.zendesk_ticket_routing` with `ticket_id`,
`predicted_skill`, `confidence`, `model_version`, and `routed_at`. The gate is
pooled "any skill versus none" at a threshold chosen on the gold set, not a
per-skill threshold. Verbal confidence is replaced with agreement across 5
sampled runs once volume justifies it.

v1 surfaces the prediction and does nothing else. `queue()` in the ticket skill
shows `predicted_skill` beside each ticket. The agent runs the skill in their
own session, with their own identity, the repo's hooks, and their own MCP
connectors. Nothing posts to Zendesk.

Two facts rule out an automated second stage in v1, and they are independent:

- The Airbyte Zendesk sync runs at `30 2 * * *` and `0 5 * * *`
  (`code_locations/kipptaf/airbyte/schedules.py`), so the warehouse sees a
  ticket 17 to 21 hours after filing. Runbook-shaped tickets close in a median
  of about 12 business hours. A warehouse-fed sensor delivers drafts after the
  human is done.
- A Dagster run pod has none of the skills, rules, PII hooks, 1Password
  bootstrap, or person-scoped MCP connectors the skills depend on. The image
  copies only `src/teamster` and `src/dbt`. Running a skill there means
  re-plumbing every skill for headless use without the repo's guardrails, and
  the agent transcript would land in Dagster+ event logs.

Where the v1 router call runs is open: a Dagster schedule polling the Zendesk
incremental export through the existing read-scope `ZendeskResource`, or a step
inside `queue()` itself. The API key follows the normal path if Dagster hosts
it: 1Password, then the k8s secret, then both `dagster-cloud.yaml` blocks.

### 8. Feedback

An optional tag applied by 2 primary assignees during the August crunch will not
produce usable labels. v1 adds a required-on-solve dropdown that appears only
when a prediction exists, through a Zendesk conditional field keyed on a hidden
"prediction present" checkbox: used, edited, wrong skill, not needed. Tag and
field changes already flow into `ticket_audits`, so the outcome reaches BigQuery
with no new pipeline.

Each month, audit 20 to 30 randomly sampled unrouted tickets for recall. The
feedback field only ever sees tickets the router fired on, so without this a
future trained model learns the router's blind spots.

Track the field's fill rate weekly. Below a threshold, the loop is turned off
and the fill rate is the next problem.

## Not in scope

- Posting anything to Zendesk under any identity. The ticket skill's
  draft-and-paste contract stands. If posting is ever revisited, it needs a
  dedicated light-agent identity limited to private notes, sandbox verification
  of trigger side effects, exclusion of that `author_id` from labeling and
  metrics, and the request-body logging in `libraries/zendesk/resources.py`
  turned off.
- A trained classifier. Reconsider when the feedback field has produced a year
  of human-confirmed labels.
- Groups other than Data and Teaching & Learning.
- Incident-burst handling, runtime caps, and request-complete gating. These
  belong to the automated stage that v1 does not build; they are recorded in
  #5803 for that stage.

## Open questions

- Legal's answer on the Console key (step 0).
- Whether internal notes change labels enough to keep sending them.
- Where the v1 router call runs (step 7).
- The restricted dataset name and expiration.
