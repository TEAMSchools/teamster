# Cube Data Issue Notice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A model-invoked skill, `cube-data-issue-notice`, that announces
Cube-affecting GitHub issues in #cube-claude-power-users and tracks each to a
verified fix in the post's thread.

**Architecture:** 1 skill folder (`SKILL.md` plus `references/templates.md`)
holds the 4 procedures and the post templates. The root `CLAUDE.md`
issue-opening bullet and `pr-ci-review` each gain 1 pointer to it. The GitHub
issue stores a marker comment with the Slack message `ts`; every later procedure
reads that marker.

**Tech Stack:** Claude Code skills (markdown), Slack MCP (`slack_send_message`,
`slack_add_reaction`, `slack_read_thread`), GitHub MCP and `gh api`,
`uv run dbt ls`, `rg`, Cube MCP (`meta`, `load`).

**Spec:** `docs/superpowers/specs/2026-10-02-cube-data-issue-notice-design.md`

## Global Constraints

- Channel: `C0BPH5STTTQ` (#cube-claude-power-users). Test channel: the user's
  Slack self-DM, `U1X7BAMFH`. No test post goes to `C0BPH5STTTQ`.
- Every Slack post: full preview in the terminal, sent with `slack_send_message`
  only after the user's explicit yes. Never `slack_send_message_draft`.
- `slack_send_message` takes standard markdown: `**bold**`, `_italic_`. Never
  Slack mrkdwn `*bold*`.
- PII gate: aggregates at school level or broader; every count 10 or more; no
  student-level rows, names, or ids.
- Post text never names a model, column, cube, or view.
- Notice marker: `Cube power users notice: <permalink>` plus
  `<!-- cube-notice ts=<message_ts> -->`. Resolved marker:
  `Cube power users notice resolved: <permalink>` plus
  `<!-- cube-notice-resolved -->`.
- No scheduled agent ever posts. The `cube` label is not a marker.
- Skill prose follows `writing-for-agents` (positive phrasing, leading words,
  completion criteria) and `.claude/rules/claude-md-editing.md` (bold only in
  the root _Never_ block).
- Lint every new or edited markdown file with
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from the worktree root. Run `trunk fmt <files>` first if prettier flags
  formatting.
- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-cube-data-issue-notice`
  (abbreviated `$wt` below; spell it out in commands). Stage with `git add -u`
  or by new-file path; never `-A`.

## Review Focus

1. An issue whose snake_case names are not models (CTE names in a diagnostic
   query, such as `int_assessments__score_anchors` in #5692). Expected: `dbt ls`
   ignores them; if no real model remains, Claude asks the filer instead of
   reporting "no Cube impact." Pinned in Task 4 step 2.
2. A conformed dim (for example `dim_students`) that many views join through a
   non-first `join_path` segment. Expected: every view that joins the cube is
   named, not just views that start from it. Pinned in Task 4 step 3.
3. `resolve` on an announced issue that is not fixed yet. Expected: Cube
   verification fails, Claude reports what Cube returned, and nothing posts.
   Pinned in Task 4 step 6.
4. Formatting. Expected: the post renders bold, bullets, links, and emoji in
   Slack, with no literal asterisks. Pinned in Task 4 step 7.
5. A small count in the issue body (#5692: "K-8 rows lose 0 to 2 scores each").
   Expected: the draft drops the number and says "close to complete." Pinned in
   Task 4 step 4.

---

### Task 1: Post templates

**Files:**

- Create: `$wt/.claude/skills/cube-data-issue-notice/references/templates.md`

**Interfaces:**

- Produces: 4 headed sections the skill points at by name: `## Top post`,
  `## Fix in progress`, `## Resolution`, `## Worked example: #5692`.

- [ ] **Step 1: Write the file**

Write exactly this content:

````markdown
# Cube data issue notice templates

Post text uses standard markdown, because `slack_send_message` converts it
(`**bold**`, `_italic_`, `[text](url)`). Replace every `<...>`. Delete a bullet
that does not apply; keep every heading line.

## Top post

```text
:rotating_light: **Data issue: <plain-language name of the data>**
**Status at posting:** :red_circle: Investigating

**What's affected**
• **Unavailable:** <data Claude cannot see at all>
• **Untrustworthy:** <data Claude can see but is wrong, and how: undercounted, rates too high or too low, wrong school>

**Who this touches**
<regions, schools, grades, subjects, years>

**Not affected**
<what is still fine, especially another place to get the same numbers>

**What to do for now**
• <the workaround: where to get the right number instead>
• <if you already shared numbers from this data, what to do with them>

**Next update:** in this thread when a fix is underway :thread:
_Tracking: [#<n>](https://github.com/TEAMSchools/teamster/issues/<n>)_
```

## Fix in progress

Thread reply, not sent to the channel. Add the `Expected:` line only when
someone gave a date.

```text
:large_yellow_circle: **Fix in progress.** <1 plain sentence on what is changing>. We'll post here once it's confirmed in Cube.
**Expected:** <date>
```

## Resolution

Thread reply with `reply_broadcast: true`. Use the partial form when some
announced items are still open.

Full:

```text
:large_green_circle: **Fixed:** <data name> is now complete and accurate in Cube, starting with your next chat.
**What changed:** <1 sentence, for example "High school scores are back, so high school proficiency rates will go up.">
**If you pulled numbers before <date>:** <re-run them, or how far off they were>
```

Partial:

```text
:large_green_circle: **Partly fixed:** <fixed items> are now accurate in Cube, starting with your next chat.
**Still open:** <items>. We'll post here when those are fixed too.
**If you pulled numbers before <date>:** <re-run them, or how far off they were>
```

## Worked example: #5692

Posted 2026-10-02 as
<https://kippnj.slack.com/archives/C0BPH5STTTQ/p1790975134928079>, before the
status line read "Status at posting."

```text
:rotating_light: **Data issue: High school state test scores**
**Status:** :red_circle: Investigating

**What's affected**
• **Untrustworthy:** NJ high school state test results (NJSLA ELA09 and ALG01, plus NJGPA). Cube is missing about two-thirds of high school scores. The students left out aren't a random group, so **proficiency rates are wrong, not just counts**. For example, KHS ELA09 shows 13% proficient in Cube but is really 22%.
• **Untrustworthy (smaller gap):** About 1 in 10 state scores are missing across most years in NJ and Florida.
• **Possibly unavailable:** Miami 2025-26 state scores may not appear at all. We're still checking this one.

**Who this touches**
High schools (NCA, NLH, KHS) most of all, plus grade 8 Algebra I. K-8 NJ results are close to complete.

**Not affected**
The STAT Tableau dashboard. It doesn't read from Cube.

**What to do for now**
• For high school state test results, use the STAT dashboard, not Claude.
• If you've shared HS proficiency rates from Claude, treat them as too low.

**Next update:** in this thread as soon as we have a fix timeline :thread:
_Tracking: [#5692](https://github.com/TEAMSchools/teamster/issues/5692)_
```

What the example does right:

- The issue's root cause (an INNER join in an intermediate model) appears
  nowhere. The post says what is wrong with the numbers.
- "Rates are wrong, not just counts" tells readers that a smaller sample is not
  the only problem.
- The workaround names a specific other tool.
- The unverified Florida 2026 finding is hedged.
- "K-8 rows lose 0 to 2 scores each" became "close to complete": the gate drops
  counts under 10.
````

- [ ] **Step 2: Lint**

Run from `$wt`:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-data-issue-notice/references/templates.md </dev/null 2>&1 | tail -n 15`
Expected: `✔ No issues`. If prettier flags formatting, run `trunk fmt` on the
file, re-check, and confirm the `text` blocks are unchanged (`git -C $wt diff`
shows only prose rewrapping).

- [ ] **Step 3: Commit**

```bash
git -C $wt add .claude/skills/cube-data-issue-notice/references/templates.md
git -C $wt commit -m "feat(claude): add Cube data issue notice post templates" -m "Refs #5695" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The skill

**Files:**

- Create: `$wt/.claude/skills/cube-data-issue-notice/SKILL.md`

**Interfaces:**

- Consumes: the 4 section names from Task 1.
- Produces: skill name `cube-data-issue-notice`; procedure names `announce`,
  `update`, `resolve`, `sweep` (Task 3 points at `update` and `resolve` by
  name).

- [ ] **Step 1: Write the file**

Write exactly this content:

````markdown
---
name: cube-data-issue-notice
description:
  Use right after filing a GitHub issue that may affect data served through
  Cube, when a PR that closes an announced issue opens or merges, or when asked
  to announce, update, resolve, or sweep Cube data issue notices in the Cube
  power users Slack channel.
---

# Cube data issue notice

The #cube-claude-power-users channel (`C0BPH5STTTQ`) holds the staff who use
Claude and Cube for analysis. They are not technical. A notice tells them which
data is unavailable, which is untrustworthy and how, and what to use instead.
Its thread tracks the issue until the fix is verified in Cube.

Read [`references/templates.md`](references/templates.md) before drafting any
post.

## Non-negotiables

- Preview every post in full in the terminal. Send it with `slack_send_message`
  after the user's explicit yes in their own message. The thread depends on the
  message `ts` that a direct send returns.
- The issue is the record. After every top post and every resolution, comment
  its marker on the issue. Every later procedure starts from the marker.
- PII gate before every preview: numbers appear only as aggregates at school
  level or broader, every count is 10 or more, and the post names no student and
  carries no student-level row or id. When a number fails the gate, describe it
  in words ("close to complete") and keep the gate.
- Name data the way a reader names it ("high school state test scores"). Model,
  column, cube, and view names stay in the GitHub issue that the post links.

## Markers

Notice marker, commented on the issue after the top post:

```text
Cube power users notice: <message_link>
<!-- cube-notice ts=<message_ts> -->
```

Resolved marker, commented after the resolution reply:

```text
Cube power users notice resolved: <message_link>
<!-- cube-notice-resolved -->
```

`message_link` and `message_ts` come from the `slack_send_message` result. The
visible phrase is what `sweep` searches. Read markers with
`gh api repos/TEAMSchools/teamster/issues/<n>/comments --jq '.[].body'`.

## announce

Trigger: right after `issue_write` creates an issue, or "announce #N."

1. Lineage check. From the checkout root (the worktree root in a worktree):

   ```bash
   names=$(gh api repos/TEAMSchools/teamster/issues/<n> --jq .body \
     | rg -o '\b(stg|int|base|bridge|dim|fct|rpt)_[a-z0-9_]+' | sort -u \
     | sed 's/$/+/' | tr '\n' ' ')
   (cd src/dbt/kipptaf && uv run dbt ls --select ${names} \
     --resource-type model --output name --quiet) > <scratchpad>/downstream.txt
   rg -o --no-heading 'sql_table: kipptaf_marts\.(\w+)' -r '$1' \
     src/cube/model/cubes | rg -wFf <scratchpad>/downstream.txt
   ```

   `<scratchpad>` is the session scratchpad path from the system prompt. Each
   hit is `<cube file>:<table>`. The cube name is the first `- name:` in that
   file. Find its views with
   `rg -l "join_path: ([a-z_]+\.)*<cube>\b" src/cube/model/views`; a view counts
   when the cube appears anywhere in a `join_path`.

   - Views found: continue, and keep the view list for drafting.
   - `downstream.txt` holds models but no cube matches: tell the user in 1 line
     that the issue does not reach Cube. The procedure ends.
   - `downstream.txt` is empty (the issue names no model, or every name was a
     CTE or column): ask the filer whether the issue affects Cube data.

2. Draft from `## Top post`. Use `cube meta` on the affected views to learn what
   readers call the data.
   - Label each affected item Unavailable or Untrustworthy. Every Untrustworthy
     item says how it is wrong.
   - "Not affected" and "What to do for now" carry real content. When the issue
     offers no workaround, ask the filer for one.
   - Hedge every finding the issue marks unverified or not investigated.
3. Run the PII gate. Preview. Post to `C0BPH5STTTQ` on a yes.
4. Comment the notice marker on the issue.

Done when the post is live and the issue carries its notice marker, or the user
has heard why no post went out.

## update

Trigger: right after `create_pull_request`, when the PR body contains
`Closes #N`, `Fixes #N`, or `Resolves #N` and issue N carries a notice marker
(`Refs #N` is a reference, not a fix). Also "update #N."

1. Read `ts` from the notice marker.
2. Draft from `## Fix in progress`: 1 plain sentence on what the PR changes.
3. Preview. On a yes, reply with `thread_ts` set to the marker's `ts` and
   `reply_broadcast` off.

Each closing PR gets its own reply; the preview lets the user skip one.

## resolve

Trigger: the session sees a closing PR merge (a `pr-ci-review` watch, or the
user says so), or "resolve #N."

1. Read the issue's comments. A resolved marker means the resolution is already
   out: tell the user and stop. No notice marker means nothing was announced:
   stop.
2. Verify through Cube, the path readers take. Re-run the issue's "fixed means"
   check with `cube load`; when that check is BigQuery-only, run it and compare
   Cube's numbers to it. When the issue states no check, ask the user what fixed
   looks like.
   - Pass: continue.
   - Fail, or prod has not rebuilt yet: report what Cube returned. Offer a
     check-back after the next prod build that re-runs this step and reports to
     the user. A check-back reports; posting stays in this procedure, behind a
     yes.
3. Draft from `## Resolution`. Use the partial form when some announced items
   are still open.
4. Run the PII gate. Preview. On a yes, reply with `thread_ts` from the marker
   and `reply_broadcast: true`.
5. When every announced item is fixed, add `white_check_mark` to the top post
   with `slack_add_reaction` (channel `C0BPH5STTTQ`, timestamp from the marker).
   The connector cannot edit messages, so the reaction is the top post's only
   change.
6. Comment the resolved marker on the issue.

Done when the resolution is live and the issue carries its resolved marker, or
the user has the Cube result that blocked it.

## sweep

Trigger: "sweep Cube notices," or any time someone closed an announced issue
outside Claude (another person, the GitHub UI, the terminal). Manual only:
scheduled-agent output is a forbidden PII destination.

1. Find announced issues:

   ```bash
   gh api -X GET search/issues \
     -f q='repo:TEAMSchools/teamster is:issue "Cube power users notice" in:comments' \
     --jq '.items[] | "\(.number) \(.state) \(.title)"'
   ```

   Drop each issue whose comments carry the resolved marker.

2. Closed issues: run `resolve` on each, 1 preview and 1 yes per issue.
3. Open issues: list each with its last thread reply (`slack_read_thread` with
   the marker's `ts`) so the user can pick any that need an `update`.

Done when every announced issue is resolved, blocked by a failed Cube check, or
listed for the user.
````

- [ ] **Step 2: Lint**

Run from `$wt`:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-data-issue-notice/SKILL.md </dev/null 2>&1 | tail -n 15`
Expected: `✔ No issues`. Fix formatting with `trunk fmt` if flagged.

- [ ] **Step 3: Confirm the skill loads**

Run:
`rg -n '^name: cube-data-issue-notice$' $wt/.claude/skills/cube-data-issue-notice/SKILL.md`
Expected: 1 hit on line 2. The skill lives only in the worktree, so it is not in
this session's skill list (the session loads skills from the main checkout).
Task 4 runs its procedures by reading the file.

- [ ] **Step 4: Commit**

```bash
git -C $wt add .claude/skills/cube-data-issue-notice/SKILL.md
git -C $wt commit -m "feat(claude): add the cube-data-issue-notice skill" -m "Refs #5695" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Wire the triggers

**Files:**

- Modify: `$wt/CLAUDE.md:37-41` (the "Opening an issue via
  `mcp__github__issue_write`" bullet)
- Modify: `$wt/.claude/skills/pr-ci-review/SKILL.md:92` (append after the
  `dagster-cloud-deploy / deploy` bullet, before
  `## dbt Cloud CI builds only kipptaf`)

**Interfaces:**

- Consumes: skill name `cube-data-issue-notice`; procedures `update` and
  `resolve`; the visible phrase `Cube power users notice:`.

- [ ] **Step 1: Edit the root CLAUDE.md bullet**

Read `$wt/CLAUDE.md` with the Read tool, then replace:

```markdown
Label with the conventional-commit type, source systems, and `dagster`/`dbt`
when applicable.
```

with:

```markdown
Label with the conventional-commit type, source systems, and `dagster`/`dbt`
when applicable. Then invoke `cube-data-issue-notice` to check whether the issue
reaches Cube.
```

- [ ] **Step 2: Add the pr-ci-review bullet**

Read `$wt/.claude/skills/pr-ci-review/SKILL.md` with the Read tool, then insert
after the bullet ending `whose config you edited.` and its blank line:

```markdown
- A PR whose body closes an issue (`Closes`, `Fixes`, `Resolves #N`) that
  carries a `Cube power users notice:` comment: right after opening it, run
  `cube-data-issue-notice` `update`; when it merges, run `resolve`.
```

- [ ] **Step 3: Lint both files**

Run from `$wt`:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix CLAUDE.md .claude/skills/pr-ci-review/SKILL.md </dev/null 2>&1 | tail -n 15`
Expected: `✔ No issues`.

- [ ] **Step 4: Confirm the pointers resolve**

Run:
`rg -n 'cube-data-issue-notice' $wt/CLAUDE.md $wt/.claude/skills/pr-ci-review/SKILL.md`
Expected: 2 hits, 1 per file. Run
`rg -n '^## (update|resolve)$' $wt/.claude/skills/cube-data-issue-notice/SKILL.md`.
Expected: 2 hits, so both procedure names in the pointer exist.

- [ ] **Step 5: Commit**

```bash
git -C $wt add -u
git -C $wt commit -m "feat(claude): point issue filing and PR review at cube-data-issue-notice" -m "Refs #5695" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Live verification

No files change unless a step fails. A failure gets fixed in `SKILL.md` or
`templates.md` and lands as a new commit in step 8.

**Interfaces:**

- Consumes: everything from Tasks 1 to 3.

- [ ] **Step 1: Positive lineage on #5692**

Run the `announce` step 1 block with `<n>` = `5692`. Expected: `downstream.txt`
contains `fct_assessment_scores_enrollment_scoped`; the cube hit is
`src/cube/model/cubes/student_assessments/student_assessment_scores.yml:fct_assessment_scores_enrollment_scoped`;
the views list contains `student_assessment_scores_view.yml`.

- [ ] **Step 2: Negative lineage on #5677, plus non-model names**

Run the same block with `<n>` = `5677`. Expected: `downstream.txt` holds
`rpt_deanslist__promo_status` only; no cube hit; the procedure says the issue
does not reach Cube. Then confirm the #5692 run did not fail on
`int_assessments__score_anchors` (a CTE name, not a model): `dbt ls` printed
results for the real models.

- [ ] **Step 3: Conformed dim fan-out**

Run the cube and view steps with `downstream.txt` holding `dim_students` (write
it by hand). Expected: the view search lists more than 1 view across
`src/cube/model/views/`. If it lists only views whose first `join_path` segment
is the cube, fix the regex in `SKILL.md` and re-run.

- [ ] **Step 4: Dry-run draft for #5692**

Draft the top post for #5692 from the skill and templates, without posting.
Check the draft against the PII gate and the template. Expected: no count under
10 (the issue's "0 to 2 scores each" is gone), no model, cube, or view name, and
"Not affected" names the STAT dashboard. Show the draft to the user.

- [ ] **Step 5: Backfill the #5692 marker and test the sweep search**

Post this comment on #5692 with `mcp__github__add_issue_comment`:

```text
Cube power users notice: https://kippnj.slack.com/archives/C0BPH5STTTQ/p1790975134928079
<!-- cube-notice ts=1790975134.928079 -->
```

Then run the `sweep` step 1 search. Expected: `5692 open ...` appears. GitHub's
search index can lag a few minutes; re-run up to 3 times over 10 minutes. If it
never appears, stop and ask the user. The fallback is a new dedicated label (for
example `cube-notice`), which changes the spec's marker decision.

- [ ] **Step 6: resolve on an unfixed issue posts nothing**

Run `resolve` steps 1 and 2 on #5692. Expected: step 1 finds the notice marker
and no resolved marker; step 2's Cube `load` (spring 2026 NJSLA, ELA09 and ALG01
`count_scored` by school) still shows the undercount; Claude reports the numbers
and offers a check-back. No Slack call runs.

- [ ] **Step 7: Slack mechanics in the self-DM**

Ask the user for a yes, then post to channel `U1X7BAMFH`:

1. The `## Top post` template filled with test text ("TEST: ignore").
2. A thread reply from `## Fix in progress` with `thread_ts` from step 1's
   result and `reply_broadcast` off.
3. A thread reply from `## Resolution` with `reply_broadcast: true`.
4. `slack_add_reaction` `white_check_mark` on the step 1 message.

Expected: each call returns a `message_ts` or success; the user confirms in
Slack that bold, bullets, links, and emoji render with no literal asterisks,
that the broadcast reply shows in the conversation, and that the reaction sits
on the top post. A failed `reply_broadcast` or reaction in a DM means retesting
in a channel the user names; never `C0BPH5STTTQ`.

- [ ] **Step 8: Commit any fixes**

If steps 1 to 7 changed a file:

```bash
git -C $wt add -u
git -C $wt commit -m "fix(claude): <what the live test caught>" -m "Refs #5695" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Open the PR

**Files:** none new.

- [ ] **Step 1: Final lint on every touched markdown file**

Run from `$wt`:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix CLAUDE.md .claude/skills/pr-ci-review/SKILL.md .claude/skills/cube-data-issue-notice/SKILL.md .claude/skills/cube-data-issue-notice/references/templates.md docs/superpowers/plans/2026-10-02-cube-data-issue-notice.md </dev/null 2>&1 | tail -n 15`
Expected: `✔ No issues`.

- [ ] **Step 2: Push**

Run: `git -C $wt push 2>&1 | tail -n 3` Expected: the push updates the existing
remote branch (no `* [new branch]`).

- [ ] **Step 3: Open the PR**

Build the body from `.github/pull_request_template.md`, plain language per
`.github/PLAIN_LANGUAGE.md`, `Closes #5695`, and the Task 4 results (what
passed, and anything skipped) in the "For Claude" fold-out. `claude-review`
skips markdown-only PRs, so drop the "Review the Claude Code Review comment"
checkbox. End with the Claude Code attribution line. Open it with
`mcp__github__create_pull_request` (base `main`), then confirm the returned
title and body match.

- [ ] **Step 4: Offer the follow-ups**

Offer to watch CI. On a yes, invoke `pr-ci-review` and arm a Monitor in the same
turn.
