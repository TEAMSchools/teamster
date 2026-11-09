# Cube triage, owner answers in chat, and the builder: design

Issues: #6150 (scope comment of 2026-10-28) and #6157. Ships in PR #6160 with
the validator. Builds on
[2026-10-26-cube-validation-and-build-skill-design.md](2026-10-26-cube-validation-and-build-skill-design.md);
this document replaces that design's "Part 2: the builder" and adds 2 pieces
before it.

## Intent

The validator works: the attendance run proved 13 comparisons and produced 26
owner questions. 2 steps after it still ran by hand, and a third was never
built:

1. **Triage before the owner.** The analyst, with Claude, read Cube's member
   descriptions and `ai_context` and closed 9 of the 26 questions without the
   owner, and an open issue (#4927) settled parts of 5 more. Most "owner
   questions" were answered by evidence the tool could have gathered.
2. **The owner's answers.** The owner is the analyst's boss: he knows the
   policy, is not a coder, and should answer in VS Code chat, not by writing
   GitHub comments.
3. **The builder.** Adding a dashboard's missing measures to Cube is still a
   manual reconstruction of formulas, filters and lineage.

## Goals

1. Close everything the evidence answers before a question reaches the owner,
   with the analyst approving in one batch.
2. Let the owner answer each remaining question in chat, with the information to
   judge it and checks he can run himself.
3. Record the owner's answers as decisions the analyst picks up like a code
   review.
4. Given a dashboard, inventory what Cube has and lacks, plan the missing pieces
   in tiers, then build them as reviewable pull requests, each proven against
   the dashboard before it merges.

## Non-goals

- Data quality at the source. A "the source data is wrong" answer opens an issue
  for that data's owner; the validator does not monitor data.
- CI (#6158), still later.
- Changing any production dashboard or schedule.

## Anti-goals (failure even if it technically works)

- **Timing reported as a difference.** Every comparison, before or after a
  merge, is pinned to 1 fact build; anything the tool cannot pin, it refuses.
- **A duplicate measure.** The builder never adds a member Cube already has
  under another name or with the same SQL.
- **An owner question the evidence already answers**, or one the owner cannot
  understand without asking the analyst.
- **Student-level detail, or anything identifying a staff member, on GitHub.**
  Counts and codes only, under the small-cell rule. Never on GitHub, in git, or
  in a decision: a student's name, number or row; a staff member's name, email
  or row (a teacher or homeroom cut is a staff row). These stay in local chat.

## People

- **The analyst** builds Cube, runs the validator, triages, and drives the
  builder.
- **The owner** (today the analyst's boss) answers policy questions in VS Code
  chat. He has a checkout of this repo with Claude Code, a GitHub account, and
  BigQuery console access to the base tables, but he never edits validation
  files or runs the validator.
- **A data's domain owner** (for example, Miami's attendance data) gets an issue
  when the owner finds a source-data problem.
- **Reviewers**: analytics engineers review Cube changes; data engineers review
  dbt mart changes.

## How the work is organized

**One GitHub issue per piece of work, as its hub.**

- A **validation issue** ("Validate the Attendance Dashboard in Cube") holds the
  owner's questions and his answers. Each validation round also has a small data
  PR for its validation file (proofs and decisions), even when every answer is
  "intended"; that file is what CI will read.
- A **build issue** ("Build DDI Suite in Cube") holds the builder's inventory
  and tiered plan. The builds become PRs linked to it.

**The attendance run moves out of #6160 once this design is written.** A new
validation issue; a new branch, in its own worktree, based on the validator
branch, keeping every attendance data commit; and 1 commit on #6160 that removes
the 2 attendance validation files (history kept, nothing rewritten). The
attendance session moves to that worktree. After #6160 merges, the attendance PR
is retargeted to `main`. The end-to-end test with the owner happens on that
branch once Parts A and B are built.

## Part A: context-checked triage

After `run`, before `review`, the tool gathers evidence for every open item (row
groups, cell differences, missing cuts and filters) and suggests a call. It
never applies a call and never touches GitHub.

**Evidence the tool gathers** (deterministic, offline-testable):

1. **Member docs beside each item.** The `description` and `ai_context` of the
   comparison's measure and of every member the item involves.
2. **A Cube member for a dashboard field** with no paired member: candidates by
   name, caption and description, then a value check. Reference columns compare
   exact values ("same values: map it under `filters:`"); a description match
   with different values reads "same field, different coding" (Ethnicity letters
   against `race` labels); otherwise "no candidate". Values are never compared
   or printed for an identifier column.
3. **Filters that filter nothing.** From the workbook XML: a filter that keeps
   every member, or whose field is a plain copy of a mapped field, or a
   parameter-driven display switch.
4. **A suggested call per item, with its evidence**, in the run result and in a
   machine-readable file beside `run.json`.

**What Claude adds in the skill:** a search of open GitHub issues for known gaps
(#4927 explained the Miami nulls), contradictions between a description and the
result (`pct_ontime` says Miami present days count as on time; Cube returns
blank), and a drafted reason for every suggested close, so the analyst edits
rather than writes.

**The analyst approves in a batch,** grouped by suggestion, the owner pile last:

- Close as deliberate (the docs answer it), with the quoted evidence
- Map under `filters:` (Cube has the field)
- Filters nothing
- Known issue
- Send to the owner (no evidence answers it)

The analyst replies "approve all" or "approve all but 2 and 6". Approved items
become decisions; only the owner pile reaches `review`.

## Part B: owner answers in chat

**`review`** posts the remaining questions to the validation issue as today, and
also writes them as JSON: question id, reason, the decision ids it covers across
files, both definitions, the evidence, the counts, the hand checks and the run's
moment. The JSON goes into the validation issue too, as a fenced block, so the
owner's session reads it from GitHub; it holds the same counts and codes as the
markdown, under the same small-cell rule, and nothing row-level. Claude reads
the JSON, never the markdown.

**The owner's skill** is a repo skill (he has a checkout) with a plain-language
trigger ("answer the attendance review", "walk me through issue #N"), so he
never needs the validator's name. Claude opens the validation issue, says how
many questions there are, then asks one at a time. When he asks for example
students, his session queries them with his own access, and they stay in his
chat.

**Each question shows everything up front,** in this order:

1. The question in policy words ("Which attendance codes should count as
   tardy?"), with no column names.
2. The 2 definitions side by side: the Tableau formula with code groups spelled
   out, and Cube's definition.
3. Who differs: the filters on each side, and the rows and students only one
   side counts, by school or grade (counts only; small cells masked).
4. What triage found, and why it is his call.
5. **Checks he runs himself**, independent of Claude:
   - the dashboard: which sheet, which filters to set, which cell to read, and
     the number to expect (the example cell with the biggest difference). The
     example cell is always a group: built only from reviewed columns (region,
     school, grade and the like), with 10 or more students. Never one student's
     row, and never a row for a teacher or other staff member. If no such cell
     differs, the issue says so, and his session finds an example under his own
     access, in his chat;
   - BigQuery SQL for each side, to paste into the console under his own access,
     **pinned to the run's moment** with time travel, so his numbers reproduce
     the tool's. Each returns only the example cell's number; the SQL sits in a
     collapsed block in the issue because the expanded view can be long. Tableau
     shows its last refresh, so a small difference may not match there.
6. The answer, as choices with what happens next, plus free text:

| Choice                     | Call            | What happens                             |
| -------------------------- | --------------- | ---------------------------------------- |
| The dashboard is right     | `fix_cube`      | the domain's Cube-fix issue              |
| Cube is right              | `fix_dashboard` | the domain's Asana dashboard-fix task    |
| Both fine, intended        | `deliberate`    | recorded; stays quiet on later runs      |
| The source data is wrong   | `fix_source`    | a new GitHub issue for that data's owner |
| Free text ("need to talk") | `domain_owner`  | stays open, with his note in the reason  |

He can ask follow-up questions before answering; Claude answers from the same
evidence and asks the question again.

**`fix_source` is a new call.** It covers "this is weird, investigate" and
"found it: Miami entered tardies wrong". Claude drafts a GitHub issue with the
question, both definitions, the counts, his note and what his session found; he
picks the domain owner to assign and confirms the text. That issue is the
decision's `task`. It never carries a student's name, number or row, or a staff
member's name, email or row; the domain owner is named only as the GitHub
assignee.

**The pinned checks need the run to be fresh.** Time travel reaches 7 days, so
the Q&A warns when the moment is near that limit; past it, the analyst re-runs
`run` and the questions refresh.

**At the end,** Claude shows a summary of his answers; he confirms it, and
Claude posts 1 comment on the validation issue: a readable summary plus a fenced
machine-readable block. His free-text notes become decision reasons in git, so
before posting, Claude checks them for a student's or staff member's name,
number or email (likely after he looked at example students) and asks him to
reword; `record-answers` repeats the check before writing.

**Where each fix call's `task` comes from.** Each validation file gets a
`tasks:` block naming its domain's Cube-fix GitHub issue and Asana dashboard-fix
task. An owner's `fix_cube` or `fix_dashboard` answer takes its `task` from
there; `fix_source` takes the issue his session opened. Like the other fix
calls, `fix_source` keeps its items quiet while that issue is open, and the
measure still does not read "validated".

**The analyst picks it up like a code review:** "pick up the answers on #N". A
new command, `record-answers`, reads only the comment the analyst points it at;
it shows that comment's author, and the analyst confirms before anything is
written. It writes the decisions: the call, a reason that keeps the owner's
words, and `task`. It refuses an answer whose decision ids no longer match. Then
`run` again (the decisions fingerprint covers `reason`, a safeguard the analyst
kept). The validation issue closes when every question has a decision and every
fix has its issue, PR or Asana task.

## Part C: the builder

The analyst says "build DDI Suite in Cube".

### 1. Inventory, from 3 sources

- **The gap catalog**
  ([`docs/superpowers/plans/2026-10-02-cube-gap-catalog.md`](../plans/2026-10-02-cube-gap-catalog.md)
  and its domain files): every measure and dimension on the dashboard,
  classified `cube-covered`, `mart-ready`, `mart-missing` or `workbook-only` as
  of 2026-10-02. The builder re-checks each row against today's Cube.
- **An independent review**: a fresh reviewer re-inventories the workbook from
  its XML (sheets, calculations with code groups expanded, cuts and filters)
  without seeing the catalog, so it is not anchored on it.
- **The dashboard's Asana task** in "Data Marts + Semantic Layer": its
  blocked-by builds, their open field subtasks, and its deferred and retired
  notes. A retired item (QBL) drops out; a deferred one is listed, not planned.

The result is one row per measure and dimension: in Cube (naming the member) or
missing. Where the 3 sources disagree, the row says so, and the analyst decides.

**No duplicates.** Before calling anything missing, the builder searches every
cube, not only the dashboard's view, for a member that already means it: by
name, by description, and by compiled SQL. A member whose compiled SQL equals
another's is refused.

A same-named member on another cube is a candidate, not a match. Cube has 4
`count_students` today, and each counts a different population: students with a
score, enrolled in a period, with a section enrollment, enrolled on a day. Their
compiled SQL differs, so the SQL check alone misses them, and the name check
alone would wrongly call them one measure. For each candidate the builder shows
the analyst what it counts (the key it counts, its table's grain, its filters)
beside what the dashboard counts, and one of 3 verdicts:

1. **Same population, already in the dashboard's view:** reuse it; nothing is
   built.
2. **Same population, on a cube the view does not include:** add that cube to
   the view (a tier 2 change), not a copy of the measure.
3. **Different population:** a new measure is allowed. Its name says which
   students it counts (`count_students_with_attendance`, not `count_students`),
   and its description says how it differs from the others. `count_students`
   means the enrollment headcount and nothing else, on every view.

The analyst confirms each verdict before the plan is written.

Dimensions follow the same path. The DDI Suite workbook showed 4 kinds of field:
already in Cube under another name (map it under `filters:`), plain `rpt`
columns Cube lacks, workbook calculations with business logic, and
presentation-only fields (parameters, URLs, permission fields), which are
ignored.

### 2. The tiered plan

Each missing piece sits in the shallowest tier that builds it:

1. Every member exists: only a comparison and a proof.
2. New Cube members over columns a mart already has.
3. New columns on an existing fact or dimension table, then their members.
4. A whole new cube over an existing mart.
5. A new fact table: a new dbt mart, then everything above.

**Where it lands:** the build issue holds the inventory, the source
disagreements and the plan. Asana changes only where something was missed (a
measure no field subtask names, a dependency the blocked-by list lacks), shown
in the build issue first and made after the analyst approves.

### 3. Building, in 3 PR types

After the analyst approves the plan, the builder builds, shallowest tier first:

1. **YAML only**: new measures over members already present, and their
   validation comparisons. A simple review.
2. **Cube adds or changes**: new dimensions, joins, a new cube. Analytics
   engineer review.
3. **Fact adds or changes**: new columns or a new mart in dbt. Data engineer
   review. A type 3 PR merges before the type 2 that reads its column.

**Every PR is proven before it merges.**

- **Types 1 and 2** run the validator against a **local Cube server** over the
  branch's model (the `CUBEJS_SCHEMA_PATH` copy in
  `.claude/rules/cube-authoring.md`). A flag points it at a Cube Cloud Dev Mode
  deployment instead.
- **Type 3**: the local Cube copy reads the analyst's dbt dev build of the mart,
  and the validator reads the dev table. The moment is that dev build, found in
  BigQuery's job history like a production build, so the dashboard side still
  rebuilds at the matching moment.
- Each PR's description says what was proven, at which moment, against which
  branch.

When every tier is done, a validation issue runs the whole dashboard end to end
(Parts A and B), and the dashboard's Asana stage subtasks move from "Built in
Cube" toward "Matches within tolerance".

### 4. What ships in #6160, and the first real test

The builder ships in #6160 as the commands it needs and its skill runbook,
proven by offline tests. The steps that need judgment (reading the 3 sources,
the independent review, sorting a field into its group, choosing a tier) are
skill steps; the deterministic parts are commands: walking Cube's members with
their compiled SQL for the duplicate check, the workbook re-inventory, and the
comparison of the 3 sources into the inventory.

The first real test is DDI Suite, outside #6160: its own build issue and PRs,
based on #6160's branch until it merges, the same way the attendance run moves
out.

## Changes to the validator these need

- Evidence gathering, suggested calls and their machine-readable file (Part A).
- `review` also writes its questions as JSON, with hand checks (Part B).
- A `record-answers` command (Part B).
- A `fix_source` call, with `task` required like the other fix calls.
- `record-answers` refuses a reason that contains a student's or staff member's
  name, number or email.
- The review's footnote reads "identifiers of students and staff are hidden"
  (today: "student identifiers").
- The Cube client accepts plain `http` for `localhost` only; every other URL
  stays https-only, as the security scan required.
- A moment can come from a dev build of a fact, not only production.

## Constraints

- The tool posts nothing. Claude posts only what the analyst or the owner
  approved: triage closes, the owner's comment, a `fix_source` issue, Asana
  edits, pull requests.
- No PII in decisions, reasons, issues, comments or PRs
  (`.claude/rules/ferpa-pii.md`), and nothing that identifies a staff member.
  The value check skips identifier columns. The review already shows values only
  for its reviewed columns and redacts every other one, so a teacher or homeroom
  column fails closed; the new JSON, hand checks and `fix_source` issue use the
  same list. Example students in the owner's chat stay local.
- Time travel's 7-day window bounds every pinned check.
- BigQuery spend (Charlie's review on #6160). Every query the new commands run
  goes through the validator's warehouse: triage's value checks, the builder's
  dev-build moment lookup, and every proof. Each query is priced before it runs,
  counts against the run's cap and the daily cap shared by every run on the
  machine (`--max-usd-per-day`), and reuses view versions from the disk cache.
  The owner's pinned SQL runs under his own access, outside those caps, so each
  check shows its dry-run price and filters to the example cell's school and
  grade to scan as little as the table allows.
- Data commits (validation files) stay separate from tool commits. Another
  session works the same worktree, so files are staged by name.

## Decided by the analyst

- Triage before the owner; batch approval, grouped by suggestion, owner pile
  last.
- The owner answers in VS Code chat, one question at a time, with choices plus
  free text, everything shown up front.
- The owner's checks are his to run (dashboard steps and SQL), not Claude's, and
  the SQL is pinned to the run's moment.
- A 5th outcome, the source data is wrong, opens a new issue assigned to a
  domain owner.
- One issue per validation and per build, as the hub; the analyst picks up the
  owner's answers like a code review.
- The attendance run moves to its own issue and branch after this design is
  written.
- The builder's inventory comes from the gap catalog, an independent review and
  the Asana dashboard task; its plan tiers the missing pieces; it lands in a
  build issue, with Asana edits only for misses.
- The builder builds, in 3 PR types by reviewer, each proven before merge,
  against a local Cube server by default.
- Everything ships in #6160, but the builder's first real test (DDI Suite)
  happens outside it, in its own issue and PRs.
- The owner has a repo checkout with Claude Code, GitHub, and BigQuery console
  access to the base tables.
- Staff names and anything else identifying a staff member stay off GitHub, the
  same as student-level detail.
- `count_students` means the enrollment headcount only. Any other set of
  students gets a name that says which. The rule goes into
  `.claude/rules/cube-authoring.md`, and the existing measures that break it are
  renamed, in their own PR (#6176), before the DDI Suite build.

## Left to the builder

- Command names, file formats, and the owner skill's name.
- How candidates are scored for field matching, within the value rule above.
- How the independent review is run.
- Which example cell the hand checks use when several differ by the same amount.

## Calls I made (not discussed with the analyst)

- Claude drafts the reason for each suggested close.
- The owner's Q&A is a separate skill, not a mode of `cube-validation`.
- `fix_source` is the new call's name.
- A member whose compiled SQL equals another's is refused outright.
- The duplicate search covers every cube. A same-named member elsewhere gets one
  of 3 verdicts (reuse, add its cube to the view, or a new measure for a
  different population) for the analyst to confirm.
- Retired Asana items drop out of the inventory; deferred ones are listed but
  not planned.
- The builder proves on a local Cube server for all 3 PR types; the Cube Cloud
  Dev Mode flag is opt-in.
- A `tasks:` block per validation file supplies the Cube-fix issue and Asana
  dashboard-fix task; `fix_source` keeps its items quiet while its issue is
  open.
- The owner's questions reach his session as a fenced JSON block in the
  validation issue, counts and codes only.
- The pinned SQL returns only the example cell, in a collapsed block.
- The owner's pinned SQL shows its dry-run price, since it runs outside the
  validator's caps.
- `record-answers` reads only the comment the analyst names, and shows its
  author for confirmation first.
- Judgment steps of the builder are skill steps; the duplicate check, workbook
  re-inventory and 3-source comparison are commands.
