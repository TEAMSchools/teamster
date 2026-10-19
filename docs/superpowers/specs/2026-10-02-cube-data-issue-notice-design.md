# Cube data issue notice skill — design

Refs [#5695](https://github.com/TEAMSchools/teamster/issues/5695). First notice,
posted by hand for [#5692](https://github.com/TEAMSchools/teamster/issues/5692):
<https://kippnj.slack.com/archives/C0BPH5STTTQ/p1790975134928079>.

## Problem

The #cube-claude-power-users Slack channel (`C0BPH5STTTQ`) holds the staff who
use Claude and Cube for analysis. They are not technical. When a GitHub issue
makes Cube data missing or wrong, nothing tells them. They either keep using bad
numbers or stop trusting Claude.

#5692 is the model case. Cube drops about two-thirds of NJ high school state
test scores, and the students it drops are not random, so high school
proficiency rates are wrong as well as short. The root cause sits in an
intermediate model, and the issue body never says "Cube" in its first line.

## Goal

When someone files an issue that affects data served through Cube, Claude offers
to announce it in the channel. The post says which data is **unavailable**,
which is **untrustworthy** and how, what is not affected, and what to use in the
meantime. The post's thread tracks the issue until the fix is verified in Cube.

## Approach

3 shapes were considered.

- **1 — one skill, three entry points.** A new skill holds the procedures and
  templates. The root CLAUDE.md issue-opening bullet and `pr-ci-review` each
  point at it in 1 line.
- **2 — no skill.** Put the steps in the root CLAUDE.md and `pr-ci-review`.
  Rejected: `.claude/rules/claude-md-editing.md` keeps runbooks out of the root
  CLAUDE.md, and the template would load in every session.
- **3 — 1 plus a PostToolUse hook** on `issue_write` and `create_pull_request`.
  Rejected for now: `settings.json` and the hooks are protected, and the hook
  fires on every issue and PR. Add it later if the CLAUDE.md trigger gets
  skipped in practice.

Selected: 1.

## Components

### Files

- New: `.claude/skills/cube-data-issue-notice/SKILL.md`. Description triggers on
  announcing, updating, resolving, or sweeping a Cube data issue. Body holds the
  4 procedures below, the channel id, the marker formats, the PII rules, and the
  lineage commands. Write it per `writing-for-agents`.
- New: `.claude/skills/cube-data-issue-notice/references/templates.md`. The top
  post, in-progress, and resolution templates, plus the #5692 post as a worked
  example. Same layout as `csgf-data-collection/references/`.
- Edit: root `CLAUDE.md`, the "Opening an issue via `mcp__github__issue_write`"
  bullet. Add 1 clause: after creating the issue, run the
  `cube-data-issue-notice` lineage check.
- Edit: `.claude/skills/pr-ci-review/SKILL.md`. Add 1 bullet: on PR open and on
  merge, if a closed issue carries a Cube notice comment, run the skill's
  `update` or `resolve` procedure.

### Markers

The GitHub issue is the record of what was posted. Every later step reads it.

- Notice comment: the visible phrase `Cube power users notice:` followed by the
  Slack permalink, plus a hidden `<!-- cube-notice ts=<message_ts> -->`.
- Resolved comment: the visible phrase `Cube power users notice resolved:`
  followed by the reply permalink, plus a hidden
  `<!-- cube-notice-resolved -->`.

The visible phrase exists because the sweep searches GitHub, and GitHub search
may not index hidden HTML comments. Verify that during implementation.

Do not use the `cube` label as the marker. The label already exists and means
Cube code work.

## Procedures

### announce

Trigger: right after `issue_write` creates an issue, or
`/cube-data-issue-notice announce <n>`.

1. Lineage check. Collect the dbt models the issue names (file paths or model
   names anywhere in the body). Run
   `uv run dbt ls --select <models>+ --resource-type model` in
   `src/dbt/kipptaf`. Intersect the result with the
   `sql_table: kipptaf_marts.<model>` values in `src/cube/model/cubes/`, then
   map the matching cubes to the views that join them.
   - No match: say so in 1 line and stop. No offer.
   - No model named in the issue (for example, a source-system data entry
     problem): ask the filer whether it affects Cube.
2. Draft from the template.
   - Label each affected item **Unavailable** or **Untrustworthy**. An
     Untrustworthy item says how: undercounted, rates too high or too low, wrong
     school.
   - _Not affected_ and _What to do for now_ are required. If the issue gives no
     workaround, ask the filer. Do not invent one.
   - Hedge anything the issue marks unverified ("we're still checking").
   - No model, column, or view names. The GitHub link carries those.
3. PII gate. Numbers only as aggregates at school level or broader. Drop any
   count under 10. No student-level rows, names, or ids. The repo has no
   small-cell rule yet
   ([#4237](https://github.com/TEAMSchools/teamster/issues/4237)); 10 is this
   skill's threshold.
4. Preview the full message in the terminal. Post to `C0BPH5STTTQ` with
   `slack_send_message` only after an explicit yes. Not a Slack draft: a draft
   does not return the message `ts`.
5. Comment the notice marker on the issue.

### update (fix in progress)

Trigger: right after `create_pull_request`, when the body has `Closes #N`,
`Fixes #N`, or `Resolves #N` and issue N carries a notice marker. `Refs #N` does
not count. Also `/cube-data-issue-notice update <n>`.

- Reply: ":large_yellow_circle: _Fix in progress._ [1 plain sentence on what is
  changing]. We'll post here once it's confirmed in Cube." An expected date only
  if someone gives one.
- Preview, explicit yes, then a thread reply (`thread_ts` from the marker, no
  broadcast). A second PR for the same issue gets its own reply; the preview
  lets the user skip it.

### resolve

Trigger: the session sees the closing PR merge (`pr-ci-review` watch, or the
user says so), or `/cube-data-issue-notice resolve <n>`.

1. Read the notice marker. If a resolved marker already exists, stop.
2. Verify. Re-run the issue's "fixed means" check through Cube `load`, the path
   users take. If the issue's check is BigQuery-only, compare Cube's numbers to
   it. If the issue states no check, ask the user what "fixed" looks like.
   - Pass: continue.
   - Fail, or prod has not rebuilt: report what Cube returned. Offer a
     check-back after the next prod build. The check-back re-runs the check and
     reports to the user. It never posts to Slack.
3. Draft the resolution reply. If the fix covers only some announced items, say
   which are fixed and which are still open.
4. Preview, explicit yes, then a thread reply with `reply_broadcast: true`.
5. If every announced item is fixed, add a `white_check_mark` reaction to the
   top post. The Slack connector cannot edit a message, so the reaction is the
   only change to the top post.
6. Comment the resolved marker on the issue.

### sweep

Trigger: `/cube-data-issue-notice sweep`. Manual only. A scheduled run is out:
scheduled-agent output is a forbidden PII destination (root CLAUDE.md, _Never_
block).

1. Search issues for the notice phrase (`-X GET search/issues`,
   `is:issue "Cube power users notice" in:comments`). Drop issues that carry the
   resolved phrase.
2. Closed issues: run `resolve` on each, one preview and one yes per issue.
3. Open issues: list each with its last thread activity (`slack_read_thread`) so
   the user can decide whether one needs an update.

This covers issues closed outside Claude: by another person, in the GitHub UI,
or from the terminal.

## Templates

The top post's status line reads "Status at posting". Status changes go out as
thread replies, because the connector cannot edit the top post. The exact text
lives in `references/templates.md`; the #5692 post is the worked example.

## Testing

Skills have no unit tests. Done when:

1. A dry run of `announce` on #5692 reaches `student_assessment_scores_view`. A
   dry run on #5677 (DeansList promotion letter labels) finds no Cube match and
   makes no offer.
2. The #5692 notice marker is backfilled on the live post, and the sweep's
   phrase search finds it.
3. A top post, a thread reply, a broadcast reply, and the reaction all work in
   the user's Slack self-DM. No test post goes to `C0BPH5STTTQ`.
4. `trunk check --force` passes on the 4 new or edited markdown files.

## Out of scope

- The PostToolUse hook (approach 3).
- Weekly shipped-work roundups in the channel.
- Detecting data problems nobody filed.
- A repo-wide small-cell suppression rule (#4237).
