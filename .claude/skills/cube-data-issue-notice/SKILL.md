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
- The issue is the record. After every top post and every full resolution,
  comment its marker on the issue. Every later procedure starts from the marker.
- PII gate before every preview: numbers appear only as aggregates at school
  level or broader, every count is 10 or more, every rate or percentage rests on
  a group of 10 or more, and the post names no student and carries no
  student-level row or id. When a number fails the gate, describe it in words
  ("close to complete") and keep the gate.
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
   [ -n "${names}" ] || echo "NO MODEL NAMES"
   (cd src/dbt/kipptaf && uv run dbt ls --select ${names} \
     --resource-type model --output name --quiet) > <scratchpad>/downstream.txt \
     || echo "DBT LS FAILED"
   for m in ${names//+/}; do
     grep -qx "${m}" <scratchpad>/downstream.txt || echo "UNRESOLVED: ${m}"
   done
   rg -o --no-heading 'sql_table: kipptaf_marts\.(\w+)' -r '$1' \
     src/cube/model/cubes | rg -wFf <scratchpad>/downstream.txt
   ```

   `<scratchpad>` is the session scratchpad path from the system prompt.
   `NO MODEL NAMES` skips to the last bullet below. `DBT LS FAILED` means
   `downstream.txt` holds an error, not models: fix it and re-run before reading
   any result. A fresh worktree needs `uv run dbt deps` in `src/dbt/kipptaf`
   first.

   Each hit is `<cube file>:<table>`. The cube name is the first `- name:` in
   that file. Find the views for each hit's cube, including cubes that
   `extends:` it (they have no `sql_table` of their own):

   ```bash
   c=<cube>; cubes="${c}"
   for f in $(rg -l "extends: ${c}\b" src/cube/model/cubes); do
     cubes="${cubes} $(rg -m1 -o '^\s+- name: (\w+)' -r '$1' "${f}")"
   done
   for x in ${cubes}; do
     rg -U -l "join_path:\s*(>-?\s+)?([a-z_]+\.)*${x}\b" src/cube/model/views
   done | sort -u
   ```

   `-U` matters: long join paths are folded onto the next line with `>-`.

   - Views found: continue, and keep the view list for drafting.
   - `UNRESOLVED` names: each is a CTE, a column, or a model from a district
     project that kipptaf reads through `source()`. Ask the filer whether those
     names affect Cube data before you conclude anything from them.
   - `downstream.txt` holds models, no cube matches, and nothing is
     `UNRESOLVED`: tell the user in 1 line that the issue does not reach Cube.
     The procedure ends.
   - `NO MODEL NAMES`, or `downstream.txt` is empty: ask the filer whether the
     issue affects Cube data.

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
6. When every announced item is fixed, comment the resolved marker on the issue.
   After a partial resolution, leave the marker off: a later `resolve` or
   `sweep` finds the issue again and posts the final resolution. Read the thread
   first (`slack_read_thread`) so the final post covers only what the partial
   one left open.

Done when the resolution is live and, for a full fix, the issue carries its
resolved marker, or the user has the Cube result that blocked it.

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
