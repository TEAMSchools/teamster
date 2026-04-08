# Using Claude Code with Superpowers

Claude Code is an AI coding assistant that runs inside VS Code. **Superpowers**
is a plugin that gives it structured workflows — brainstorming, planning,
execution, debugging, and code review — so that complex engineering work follows
a repeatable, reviewable process instead of ad-hoc prompting.

You don't need to memorize slash commands or special syntax. You talk to Claude
in plain English and use a few **trigger phrases** to tell it which workflow to
start.

## The Big Picture

Every feature, refactor, or significant change follows this lifecycle:

```text
 You say              Claude does                       You do
 ─────────            ──────────                        ──────
 "Let's brainstorm"   Asks questions, proposes           Answer questions,
                      approaches, presents design        approve design

                      Opens GitHub issue, asks            Choose worktree or
                      worktree or branch switch           branch switch

                      Creates dev branch, writes          Review spec, share
                      spec on the branch                  issue with team

                                                         Team reviews and
                                                         discusses on the issue

 "Let's write         Turns approved spec into a          Review plan
  the plan"           step-by-step plan

 "Let's execute       Works through plan task-by-task     Monitor, unblock,
  the plan"           using subagents                     answer questions

                      Runs verification, commits,         Fill in PR checklist,
                      opens PR                            request reviews
```

## Phase 1: Brainstorm

**Trigger phrase:** "Let's brainstorm"

Tell Claude what you want to build or change. It will:

1. Explore the codebase to understand the current state.
2. Ask you clarifying questions — **one at a time**, often multiple choice.
3. Propose 2-3 approaches with trade-offs and a recommendation.
4. Present the design in sections, asking for your approval after each one.

!!! warning "Don't skip this phase"

    Every project goes through brainstorming — even "simple" ones. A config
    change, a single new model, a small refactor. The design can be short, but
    it must exist and be approved before moving on.

**Your role:** Answer questions honestly. Push back if something doesn't feel
right. Say "yes" or "looks good" to approve each section.

**When you're done:** Claude moves to Phase 2 — no files are written yet.

## Phase 2: GitHub Issue and Dev Branch

After the brainstorm conversation, Claude will:

1. Open a GitHub issue with `gh issue create` — labeled with the appropriate
   conventional commit type (`feat`, `fix`, `refactor`, etc.) and any related
   system labels.
2. **Ask you: worktree or branch switch?** These are two ways to create a
   development branch. Claude will not choose for you.
   - **Branch switch** — switches your current workspace to the new branch. One
     directory, no extra setup. Tradeoff: you can't work on `main` or another
     feature without switching back.
   - **Worktree** — creates a second checkout in `.worktrees/<branch>`. Your
     original workspace stays on its current branch, so you can run other code
     or start a separate feature in parallel. Tradeoff: two directories to
     manage, and your editor needs to open the worktree path.

   | Consideration                                               | Branch switch                  | Worktree                                    |
   | ----------------------------------------------------------- | ------------------------------ | ------------------------------------------- |
   | Single-task focus                                           | Good — one branch, one context | Unnecessary overhead                        |
   | Parallel work (e.g., reviewing a PR while coding a feature) | Must stash/switch constantly   | Each task has its own directory             |
   | Editor comfort                                              | Tabs and open files stay put   | Need to open a second window or re-navigate |

3. Create and link the dev branch. Branch names follow
   [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/):
   `<gh-username>/<commit-type>/claude-<brief-description>`.
4. Write the approved design to a **spec file** at
   `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` — on the branch, not
   `main`. Commit and push.

!!! info "Nothing is written until we're on the branch"

    Specs, code, and config all belong on the feature branch. Claude will not
    write any files while on `main`.

**Your role:** Share the GitHub issue with the team.

## Phase 3: Team Review

This happens **outside of Claude** — your team discusses the spec on the GitHub
issue.

- Team members read the spec and leave comments.
- You collect feedback: approvals, concerns, requested changes.
- If changes are needed, come back to Claude and say what needs to change. It
  will update the spec and push the changes.

!!! note "Gate"

    Do not move to planning until the team has reviewed the spec. This is the
    checkpoint where the team aligns on **what** we're building before we plan
    **how**.

## Phase 4: Write the Plan

**Trigger phrase:** "Let's write the plan"

!!! tip "Resuming work across sessions"

    If you're returning to a branch after working on something else, Claude will
    merge `main` into the branch before continuing. This keeps the branch
    up-to-date and avoids merge conflicts later.

Once the team approves the spec, Claude turns it into a step-by-step
implementation plan:

- Saved to `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.
- Each task is a checkbox (`- [ ]`) with specific actions, verification
  commands, and commit messages.
- Tasks are bite-sized (2-5 minutes each).
- The plan includes a file map showing every file that will be created,
  modified, or deleted.

**Your role:** Review the plan. Make sure the tasks make sense and nothing is
missing. Say "looks good" to approve.

## Phase 5: Execute the Plan

**Trigger phrase:** "Let's execute the plan"

Claude works through the plan using **subagents** — independent workers that
handle one task at a time:

- Each task gets a fresh subagent with focused context.
- After each task, a reviewer checks the work against the spec.
- Claude marks checkboxes as it goes so you can track progress.
- If something is blocked, Claude stops and asks you for help — it doesn't guess
  or force its way through.

**Your role:** Monitor progress. Answer questions when Claude gets stuck.
Unblock issues that require human judgment (e.g., "should we prioritize X or
Y?").

!!! warning "Don't leave Claude unattended for too long"

    Subagents work fast but they can go off track. Check in periodically,
    especially on larger plans.

## Phase 6: Verify and Open a PR

When all tasks are complete, Claude:

1. **Verifies** — runs tests, linters, and any validation commands. It must show
   you the actual passing output before claiming anything works. No "it should
   pass" — evidence only.
2. **Presents options** — typically: merge locally, push and create a PR, keep
   the branch as-is, or discard.
3. **Opens a PR** — using the repository's
   [pull request template](https://github.com/TEAMSchools/teamster/blob/main/.github/pull_request_template.md)
   with squash merge.

**Your role:** Fill in the PR self-review checklist. Request reviews from the
appropriate team members. Address CI check failures.

## Other Workflows

You won't use these every time, but they're available when you need them:

| Trigger phrase             | What it does                                                 |
| -------------------------- | ------------------------------------------------------------ |
| "Let's brainstorm"         | Explore an idea before building it (Phase 1 above)           |
| "Let's write the plan"     | Turn a spec into a step-by-step plan (Phase 4 above)         |
| "Let's execute the plan"   | Work through a plan with subagents (Phase 5 above)           |
| "Let's troubleshoot"       | Structured debugging — find root cause before fixing         |
| "Let's write tests first"  | Test-driven development — failing test before implementation |
| "Let's review the code"    | Request a code review from Claude                            |
| "Let's finish this branch" | Wrap up a dev branch — verify, PR or merge, clean up         |

## Common Mistakes

**1. Skipping brainstorm because "it's simple."** Simple things are where
unexamined assumptions waste the most time. The brainstorm can be short — but it
must happen.

**2. Executing before the team reviews the spec.** The spec is where the team
aligns. Skipping review means building something nobody agreed to.

**3. Telling Claude "it's fine" when you don't understand.** If something
doesn't make sense, say so. Claude will explain or adjust. Rubber- stamping
approvals leads to bad designs.

**4. Not checking in during execution.** Subagents work independently. If you
disappear for an hour, you might come back to a mess. Check in every few tasks.

**5. Accepting "tests should pass" without seeing output.** Claude must show you
actual passing test output before claiming success. If it says "should" or
"probably," ask it to run the tests.

## Quick Reference

```text
Phase    You say                  Claude does                 Output
─────    ───────                  ───────────                 ──────
1        "Let's brainstorm"       Design conversation         Approved design
2        (automatic)              GH issue + dev branch       Issue URL + spec file
3        (you + team)             —                           Team approval
4        "Let's write the plan"   Step-by-step plan           Plan file
5        "Let's execute the plan" Subagent execution          Completed code
6        (automatic)              Verify + PR                 PR URL
```
