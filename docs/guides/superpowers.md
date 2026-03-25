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

                      Writes spec to docs/superpowers/   Review spec
                      specs/

                      Opens GitHub issue, creates         Share issue with team
                      dev branch, commits spec

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

**When you're done:** Claude writes the approved design to a **spec file** at
`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.

## Phase 2: GitHub Issue and Dev Branch

After the spec is written, Claude will:

1. Open a GitHub issue with `gh issue create` — labeled with the appropriate
   conventional commit type (`feat`, `fix`, `refactor`, etc.) and any related
   system labels.
2. Create and link a dev branch with
   `gh issue develop <number> --name <branch> --checkout`.
3. Commit the spec to the dev branch and push it.

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
1        "Let's brainstorm"       Design conversation         Spec file
2        (automatic)              GH issue + dev branch       Issue URL
3        (you + team)             —                           Team approval
4        "Let's write the plan"   Step-by-step plan           Plan file
5        "Let's execute the plan" Subagent execution          Completed code
6        (automatic)              Verify + PR                 PR URL
```
