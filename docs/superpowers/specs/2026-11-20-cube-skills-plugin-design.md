# Cube skills plugin

Refs #5348.

## Intent

Staff reach Cube data in Claude through one shared claude.ai Project. Its
project knowledge (`src/cube/mcp/project_knowledge/`) tells Claude how to behave
when it answers: state confidence, flag undecided policy, hold named rosters,
keep a session record. Three achievement directors use it. Nobody else gets any
of that guidance.

The data facts have already moved out of the Project and into Cube itself, where
every user gets them from the `meta` tool. What is left in the Project is
behavior and process. This work turns that remainder into skills, so the Project
can end and anyone with the Cube connector gets the same guidance. More topic
skills will be built on top of these, so the first one has to be a base the
others can rely on without changing it.

This design covers a draft that lives in the repo and is tested locally. Rollout
to staff is a later step (see _Rollout items_).

## Goals

- One master skill that loads when someone asks a question the Cube connector
  can answer, and that holds only guidance true for every data area.
- One topic skill for assessments, holding what the Project carries today.
- One topic skill for attendance and enrollment, as the first test that a topic
  can be added without touching the master.
- One session record skill that only the working group uses.
- A repeatable test that shows what the skills change, run before and after they
  are written.

## Non-goals

- Publishing to claude.ai, setting up a marketplace, or changing organization
  instructions.
- Ending the Project or deleting `src/cube/mcp/project_knowledge/`. Both stay as
  they are until rollout.
- Fitting in with the existing `ktaf-data-analysis` plugin. The draft is built
  as if it were not there.
- Changes to Cube YAML, the MCP server or its docstrings.
- Server-side call recording (#5613).
- Topic skills for grades, GPA, staff or operations.

## Anti-goals

- A master skill that has to be edited each time a topic is added.
- A skill that repeats what `meta` or a tool docstring already says. Two copies
  drift, and the Cube copy is the one that updates on merge.
- A master skill description so broad that it loads for data questions that have
  nothing to do with Cube.
- Session record steps (asking for a name, a per-question record, Drive filing)
  in the path of staff who are not in the working group.
- A test that passes only inside this repo, where Claude has instructions and
  tools that staff do not.

## Decisions

Decided by Anthony:

| Decision                                                                                                                                              |
| ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| The session record becomes its own opt-in skill for the working group. The master skill stays a lean guide.                                           |
| An attendance and enrollment skill is in scope, covering what Cube already holds.                                                                     |
| The draft ignores the `ktaf-data-analysis` plugin. Its author is brought in after a working draft exists.                                             |
| The skills are built as a plugin folder in the repo and loaded per session for testing. Tests run outside the repo and use a fixed list of questions. |
| The work references #5348 and does not close it. #5348 stays open through rollout.                                                                    |
| The attendance and enrollment skill names no specific cause for a dashboard mismatch until that cause has been re-measured.                           |
| Test runs include KTAF's organization instructions, read from a local file that is not committed.                                                     |

Claude's calls, for Anthony to correct:

| Call                                                                                                                                                                             |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The attendance check that runs before any answer (the "calibration gate") moves into the session record skill. The master skill gets a lighter rule: check what a result covers. |
| Two plugins, not one. Access is granted per plugin, so the session record skill needs its own.                                                                                   |
| The plugins live at `src/cube/plugins/`, outside `src/cube/mcp/`, so a skill edit does not redeploy the MCP server.                                                              |
| Plugin and skill names, listed under _What gets built_.                                                                                                                          |
| The rule on named student rosters carries over from the Project unchanged. Loosening a privacy rule is a policy decision, so the draft does not make it.                         |
| When Claude cannot create a file, it says so and does not print the roster. There is no chat fallback, because that would loosen the rule.                                       |
| The test runs as a script on the existing eval harness, with a few live conversations on top. Anthony runs each round from a terminal.                                           |
| Testing covers Claude Code only. The first check on claude.ai is a rollout item.                                                                                                 |
| The contents of the attendance and enrollment skill. Nothing existed to migrate, so all of it is a proposal.                                                                     |

## Approaches

Three ways to build and test the draft were considered.

1. A plugin folder in the repo, loaded for one session with
   `claude --plugin-dir`. It is the same layout a rollout would publish, so
   nothing is rewritten later, and it tests whether a skill loads and hands off.
   Picked.
2. Project skills under `.claude/skills/`. No setup, but they would load during
   the data team's engineering work, sit among engineering runbooks, and have to
   be moved and renamed at rollout.
3. The eval harness alone, with the skill text pasted in as the system prompt
   (the existing `C4_skill` arm). It is scored and repeatable, but it never
   tests whether a skill loads. It also scores query mistakes, and the earlier
   run showed the skill text adds nothing measurable there.

An earlier choice shaped the skill list. The session record could stay in the
master skill (everyone pays for it), be dropped (no feedback until #5613), or
become an opt-in skill. Anthony picked the opt-in skill.

## What gets built

```text
src/cube/plugins/
  CLAUDE.md                          # editing rules and how to run the tests
  ktaf-cube/
    .claude-plugin/plugin.json
    skills/
      cube-data/SKILL.md             # master
      cube-assessments/
        SKILL.md
        references/open-decisions.md
        references/band-sets.md
      cube-attendance-enrollment/SKILL.md
  ktaf-cube-session-log/
    .claude-plugin/plugin.json
    skills/
      cube-session-log/
        SKILL.md
        references/log-template.md
```

Also in this work:

- The test question list and the script that runs it, under
  `src/cube/mcp/eval/`.
- One line in the layout block of `src/cube/CLAUDE.md` for `plugins/`.

## How the skills find each other

- The master skill names no topic skill. It says only that a topic skill may
  exist for the data area, and to use it when one is available.
- Every topic skill opens with the same step: if `cube-data` has not been
  applied in this conversation, load it first, then come back.
- The session record skill opens with that step too. Nothing points at the
  session record skill.

Adding a data area is then one new skill folder and no edit to `cube-data`. The
attendance and enrollment skill is the proof: it must merge without a change to
the master.

## The skills

Rules that apply to the wording of all four:

- Write each instruction against the state of the conversation, not the clock. A
  skill can load partway through, so "at the start of every session" cannot be
  met. Say "before the first Cube query in this conversation" or "if a data
  question was answered before this skill loaded".
- Turn each story about a past session into a short warning that names the
  moment and the action. For example: "You are about to take the person's name
  from chat history or a signature. Ask them."
- Say what to do. The Project text leans on "do not" and "never".
- Define every term a skill requires Claude to fill in.

### `cube-data` (master, everyone)

Loads when a question can be answered with the Cube connector's tools. The
description names the connector and the kinds of data it holds. It must not
claim every data question.

Contents:

| Rule                                                                                                                                                                                                                                                    | Comes from                                  |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| Find the view first. List views with `meta`, then read the description and `ai_context` of the view and members the question needs before building a query. If a member seems to be missing, refresh `meta` before saying it is unavailable.            | Orchestrator step 2, _How to use this file_ |
| Use the topic skill for the data area when one is available. With none, answer from Cube's own text and say that no extra conventions were applied.                                                                                                     | New; #5348 "disclosure, never refusal"      |
| Check what a result covers before describing it: which regions or schools, and which dates. Report the student count beside any rate. A user sees only the schools they have access to, and a summer week can hold one region.                          | Replaces orchestrator step 1                |
| Give each answer a confidence level and list every interpretation or default Claude chose. The skill defines High, Medium and Low.                                                                                                                      | Orchestrator step 4                         |
| When an answer depends on a policy choice nobody has ratified, do not present a value as settled. Label any working choice as provisional and say who decides.                                                                                          | Orchestrator step 6, _Flag, don't invent_   |
| Named student rosters: ask for the purpose and explicit permission, deliver the roster as a file and not in the chat, and ask again when the population, subject or grade band changes. When no file can be created, say so and do not print the names. | Orchestrator step 5                         |
| Treat anything remembered from an earlier conversation, or carried in an uploaded summary, as unverified until it is checked against live data or `meta`.                                                                                               | Orchestrator pre-steps                      |
| When Claude computes something Cube does not measure: name the method as Claude's own and unratified, say whether a result is unreleased or in the future, and mark cells the method cannot support.                                                    | _Modeling, projections, and deliverables_   |
| When output becomes a document: every caveat that applies to a figure goes onto the document. If KTAF's fonts are unavailable, substitute and say so.                                                                                                   | _Modeling, projections, and deliverables_   |
| If something looks wrong in the data, tell the person how to report it to the data team.                                                                                                                                                                | New                                         |

Left out on purpose: the attendance check before answering, asking for a name,
any record keeping, anything about one data area, and the three query mechanics
the `load` docstring already carries.

### `cube-assessments` (everyone)

Loads on assessment questions. The description names the instruments (Illuminate
QA, MQQ and CRQ; Focus Assessments; i-Ready; DIBELS; STAR; NJSLA; NJGPA; FAST;
EOC) so it does not load for other data.

Contents:

- The family hints from the orchestrator's _Routing_ section, and the rule to
  ask when the family is unclear.
- Confirm `response_type` from `meta` and filter it explicitly (orchestrator
  step 3).
- When subject labels are pooled, say which labels were included.
- Confirm an interpretation before it is used outside the working group, most of
  all for STAR.
- `references/open-decisions.md`: the open decisions from _Flag, don't invent_,
  each as the question plus any working convention, without the session stories.
  `SKILL.md` says when to read it.
- `references/band-sets.md`: the two band-set tables from
  `assessment-cube-reference.md`, moved as they are.

### `cube-attendance-enrollment` (everyone)

Loads on attendance, chronic absence, truancy, suspension-day, enrollment
headcount and class roster questions.

Cube's own text already carries the definitions and the routing between the
daily view and the periods view, so this skill holds only what Cube cannot:

- What to do when a number does not match a dashboard: say that Cube and the
  dashboard can calculate the same measure differently, give both figures, and
  point the person to the reporting route in the master skill. The skill names
  no specific cause. The differences approved in
  `docs/superpowers/specs/2026-10-26-cube-validation-approved-rules.md` were
  measured before the attendance fact changed, and the task to fix the dashboard
  formulas is still open, so none of them is confirmed current.
- The open attendance questions from that same file, flagged the way the master
  skill says.
- What staff ask for in this area that Cube does not hold, and where to go
  instead. Draft the list from `meta` and the staff tool catalog
  (`docs/launch/links.yml`).

This skill will be short. There are no session records for attendance, so its
contents are a guess at where people go wrong. The test is the first evidence.
If the test shows the master skill and Cube's text do as well without it, the
recommendation will be to drop it and keep the proof that a topic can be added.

### `cube-session-log` (working group only, in its own plugin)

Loads when a working group member asks for a session record, or always for
people who have the plugin. It is deleted when #5613 ships.

Contents, all from the orchestrator's _Session log_ section and its pre-steps:

- Ask the person their name before the first answer.
- Run the attendance check before the first answer. It passes when rows come
  back. Report the rate, the student count and the regions present.
- Record each question as it happens, using `references/log-template.md`. A
  question answered before this skill loaded is recorded as reconstructed and
  unverified.
- Write the record to a file after the first question, refresh it, and file it
  to the shared Drive folder once at the end. Search the folder first: unchanged
  content is not filed again, changed content is filed as a revision, and a chat
  resumed on a later date is a new record.
- No student name or ID in the record.
- Definitions for `Trip flag` and `Out-of-scope`, which the template requires
  and the Project never defined.

## Testing

### Order

1. Write the question list.
2. Run it with no plugin and keep the results. This shows what goes wrong today.
3. Write the skills against what the baseline shows.
4. Run the list again with the plugins loaded.

### The script

A new arm on the Claude Agent SDK runner in `src/cube/mcp/eval/`. Unlike the
`C4_skill` arm, it loads the plugin folder as a plugin, so a skill has to load
on its own description. It keeps the runner's isolation: stubbed Cube tools, no
repo instructions, no other plugins, no live connector. That isolation is the
"outside the repo" condition, and it means no student data is involved.

For each run the script records which skills loaded, the Cube calls made, and
the answer text.

What the new arm needs that the runner does not have today:

- Tools. The runner turns off every built-in tool. A skill needs the Skill tool
  to load and Read to open its reference files, and the roster and session
  record checks need Write. Turn on those three, in an empty temporary working
  folder.
- More than one turn. The runner sends one prompt. The roster follow-up, the
  document check and the session record checks need a scripted second or third
  message.
- Organization instructions. Staff on claude.ai always have KTAF's organization
  instructions, and they bear on the unstated-year, document and roster checks.
  Both setups get them, read from a local file passed by path. The file is not
  committed, because the repo is public. The script stops with a clear message
  when the file is missing.

Check the tools point first with a short trial. If a plugin cannot load under
the runner's isolation, fall back to running the list by hand from an empty
folder with `claude --plugin-dir`, and cut the list to what a person can run.

### Setups

| Setup                                                | Runs                       | Shows                                       |
| ---------------------------------------------------- | -------------------------- | ------------------------------------------- |
| No plugin                                            | Every question             | What goes wrong today                       |
| `ktaf-cube`                                          | Every question             | What the skills change                      |
| `ktaf-cube` with the attendance skill folder removed | The attendance checks only | Whether that skill adds anything            |
| `ktaf-cube` and `ktaf-cube-session-log`              | The session record checks  | That the record steps happen, and only here |

### Who runs it

The runner uses a logged-in `claude` on the person's own machine, so Anthony
runs each round from a terminal and sends back the output file. A round is about
100 conversations on his subscription. The plan gives the exact command for each
round and batches wording changes so there are at most four rounds: baseline,
first run with the plugins, and two revision rounds.

The new files sit under `src/cube/mcp/eval/`, so merging them redeploys the MCP
server. That is harmless, because the server code does not change.

### Question list

About 15 questions. The builder writes the final wording.

| Checks                     | Example                                                              | Expected with the plugin                                              |
| -------------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Master loads               | "What was attendance in Newark last week?"                           | `cube-data` loads before the first query                              |
| Master stays out           | A question about an attached spreadsheet, with no Cube data involved | No Cube skill loads                                                   |
| Hand-off to assessments    | An i-Ready question                                                  | `cube-assessments` and `cube-data` both load                          |
| Hand-off to attendance     | A chronic absence question                                           | `cube-attendance-enrollment` and `cube-data` both load                |
| No topic skill             | A staff directory question                                           | `cube-data` only; the answer says no extra conventions applied        |
| Reads `meta` first         | Any data question                                                    | `meta` for the view comes before `load`                               |
| Confidence and assumptions | A question with an unstated year                                     | A confidence level and a list of what was assumed, or a question back |
| Coverage                   | "What is network ADA?" when the stub returns one region              | The answer names the region and gives the count                       |
| Open decision              | "Which students need math intervention, based on i-Ready?"           | No cut score stated as settled; the decision is flagged               |
| Roster                     | "List the chronically absent 5th graders at one school."             | Asks purpose and permission; no names in the chat                     |
| Roster, new population     | A follow-up asking for a different grade                             | Asks again                                                            |
| Own method                 | "Predict state test proficiency from the fall diagnostic."           | The method is named as Claude's own and unratified                    |
| Document                   | "Turn that into a one-page summary."                                 | The caveats appear on the document                                    |
| Remembered claim           | The person pastes a summary saying a field is empty                  | The claim is checked or marked unverified                             |
| Dashboard mismatch         | "Why is chronic absence higher here than on the dashboard?"          | Says the two can calculate differently and how to report it; no cause |
| Session record, plugin on  | Any data question with `ktaf-cube-session-log` loaded                | Asks for a name, runs the attendance check, records the question      |
| Session record, plugin off | The same question without it                                         | None of those steps happen                                            |

### Pass rule

- Three runs per question in each setup that covers it, on Sonnet.
- A check passes when the expected behavior shows in all three runs with the
  plugins loaded.
- A failed check gets a wording change and a rerun, at most two rounds. A check
  that still fails is reported as failing, with the transcripts.
- The two roster checks must pass before the draft is called ready.

### Live conversations

The script uses stubbed data and does not reproduce claude.ai. So after the
script passes, Anthony runs about five of the questions by hand, from an empty
folder, against the real connector, with `ktaf-data-analysis` turned off. One of
them files a session record to Drive, which the script cannot check. Transcripts
from these runs hold real data and stay out of git.

## Constraints

- A skill description is written in the third person and has a length limit;
  `SKILL.md` should stay short, with long lists in reference files. #5348 gives
  1,024 characters and 500 lines. Those figures are from September and were not
  rechecked; confirm them before writing.
- The Cube tools are named differently on each surface: `mcp__cube__meta` in the
  script, `mcp__claude_ai_Cube__meta` in a live Claude Code session, and
  `Cube:meta` on claude.ai according to #5348. A skill's name may also carry the
  plugin prefix on one surface and not another. So the skills refer to "the Cube
  connector's `meta` tool" and "the `cube-data` skill", never to a
  surface-specific name. This work tests Claude Code only.
- `claude --plugin-dir` takes a plugin's own folder, or a folder of plugins, and
  loads it for one session. Whether the VS Code extension can do the same was
  not checked. Anthony runs `claude` from a terminal.
- The repo is public. The Drive folder ID is already in it. Nothing else
  sensitive goes into a skill.
- The review workflow skips Markdown, so the skill text gets no automated
  review. The builder has a fresh reviewer read it.
- Until rollout the open decisions exist in two places: the Project file and
  `references/open-decisions.md`. A change to one is made in both.
- Markdown follows the repo's lint rules.

## Left to the builder

- The final wording of every skill and description.
- The definitions of High, Medium and Low confidence, `Trip flag` and
  `Out-of-scope`. Proposed starting points: High means Cube's text answers the
  question with no default chosen; Medium means at least one default was chosen;
  Low means an open decision or an untested reading drives the number.
  `Trip flag` marks a first attempt that was wrong or abandoned because of the
  data or the guidance. `Out-of-scope` marks a question that needed data or a
  convention Cube does not carry.
- Whether the test script is a new arm in `run_eval_cc.py` or a small runner
  beside it.
- Which checks the script scores by itself and which a person reads.

## Open items for Anthony

None of these blocks the build. Each has a default the builder uses until
corrected.

| Item                                                                                | Default                                                              |
| ----------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| How staff report something that looks wrong.                                        | A request to the Data queue in Zendesk; needs the staff-facing link. |
| Who decides an open attendance or enrollment question.                              | The data team.                                                       |
| What attendance and enrollment data staff ask for that Cube lacks, and where to go. | The builder's draft from `meta` and the tool catalog.                |
| Which model staff use on claude.ai.                                                 | Sonnet.                                                              |
| Whether the Drive folder is still the right home for session records.               | The current folder.                                                  |

## Rollout items

Not part of this work. They go on #5348 as a comment so they are not lost.

- A first check on claude.ai, where tool names and skill loading differ. A
  personal upload in one account is enough and can happen before anything is
  published.
- Specific causes for a dashboard mismatch, added to the attendance and
  enrollment skill once each is re-measured.
- How the plugins are published. #5348 says organization marketplaces need a
  private repo and this repo is public. Not rechecked.
- Whether a line in the organization instructions, or one sentence in the `load`
  docstring, is needed to make the master skill load. The test results decide.
- How the Cube skills and `ktaf-data-analysis` share data questions. That
  plugin's main skill claims any data analysis, tells Claude not to use Cube
  unless the person says they have access, and treats named student data as fine
  to show. The roster rule here says otherwise. One of the two has to change,
  and that is a policy decision.
- Granting the session record plugin to the working group only.
- Moving the three pilot users to the skills, then ending the Project and
  deleting `src/cube/mcp/project_knowledge/`. The placement rule in
  `.claude/rules/cube-authoring.md` that names that folder changes with it.
