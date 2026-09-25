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
  the plan"           (subagents or Native)               answer questions

                      Runs verification, commits,         Fill in PR checklist,
                      opens PR                            request reviews
```

## Phase 1: Brainstorm

**Trigger phrase:** "Let's brainstorm"

Tell Claude what you want to build or change. It will:

1. Explore the codebase to understand the current state.
2. Ask you clarifying questions — **one at a time**, often multiple choice.
3. Propose 2-3 approaches with trade-offs and a recommendation.
4. Present the design and ask for your approval.

Claude sizes the brainstorm to the task:

- **Spike** — a quick probe to answer a question. No design document.
- **Bounded** — a small, well-understood change. A short design agreed in chat;
  no spec file, no Phases 2-3.
- **Architectural** — anything larger or riskier. A full spec, reviewed by the
  team (Phases 2-3). When in doubt, Claude picks this one.

!!! warning "Don't skip this phase"

    Every project goes through brainstorming — even "simple" ones. A config
    change, a single new model, a small refactor. The design can be short, but
    it must exist and be approved before anything is built.

**Your role:** Answer questions honestly. Push back if something doesn't feel
right, including the size Claude picked. Approve the design explicitly —
agreeing with the idea is not the same as approving the design.

**When you're done:** An architectural design moves to Phase 2 — no files are
written yet.

## Phase 2: GitHub Issue and Dev Branch

After an architectural brainstorm, Claude will:

1. Open a GitHub issue through the GitHub connector — labeled with the
   appropriate conventional commit type (`feat`, `fix`, `refactor`, etc.) and
   any related system labels.
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
5. Comment the spec's GitHub URL on the issue
   (`.../blob/<branch>/docs/superpowers/specs/...`) so the team reads it
   rendered. Link the branch, not a commit SHA, so the link keeps showing the
   current spec as Claude pushes revisions in Phase 3.

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

- Saved to `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`, with a link back to
  the spec.
- Each task lists the files it touches and what it hands to later tasks.
- Each step is one action with a result you can check (`- [ ]` checkboxes).
- The plan records decisions, not code: function signatures, test assertions,
  the spec's exact values, and the command that proves each step works. A plan
  several times longer than its spec is a warning sign.
- A **Review Focus** section names up to five ways the build could break that
  the spec implies but no task tests yet.

**Your role:** Read the saved plan itself — approving the spec or the scope does
not approve a plan you haven't seen. Make sure the tasks make sense and nothing
is missing. Say "looks good" to approve.

## Phase 5: Execute the Plan

**Trigger phrase:** "Let's execute the plan"

When the plan is approved, Claude offers two ways to run it and recommends one:

- **Subagent-driven** — each task goes to a fresh subagent, and a reviewer
  checks each task against the spec. Costs more; best when tasks are large or
  independent.
- **Native** — Claude does every task itself, then one fresh reviewer checks the
  whole branch at the end. Cheapest; best when most tasks are small.

Either way:

- Claude keeps a progress log and marks checkboxes as it goes.
- Claude does not stop between tasks to ask whether to continue. When the plan
  is ambiguous, it records a decision and keeps going.
- It stops and asks only for something destructive or irreversible, something
  security-sensitive, a push or merge to a shared branch, or a plan too broken
  to follow.

**Your role:** Pick the approach (or accept the recommendation). Answer
questions when Claude stops. Review the decisions it recorded, and push back on
any you disagree with.

!!! warning "Don't leave Claude unattended for too long"

    Claude won't pause to check in, so check in yourself — especially on
    larger plans.

## Phase 6: Verify and Open a PR

When all tasks are complete, Claude:

1. **Verifies** — runs tests, linters, and any validation commands. It must show
   you the actual passing output before claiming anything works. No "it should
   pass" — evidence only.
2. **Presents options** — merge locally, push and create a PR, or keep the
   branch as-is. Discarding the work is not on the menu: ask for it, and Claude
   will make you type `discard` to confirm.
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
| "Let's execute the plan"   | Work through a plan (Phase 5 above)                          |
| "Let's troubleshoot"       | Structured debugging — find root cause before fixing         |
| "Let's write tests first"  | Test-driven development — failing test before implementation |
| "Let's review the code"    | Request a code review from Claude                            |
| "Let's finish this branch" | Wrap up a dev branch — verify, PR or merge, clean up         |

## Choosing a Model and Effort Level

Three knobs control cost and quality, and they buy different things:

- **Model tier** (Haiku → Sonnet → Opus → Fable) buys judgment per token —
  better questions, sharper pushback, deeper design insight.
- **Effort** (`low` → `xhigh`) buys investigation — more thinking, more
  verification, more files read before answering.
- **Compaction threshold** (`/autocompact 150k`, or `autoCompactWindow` in
  settings) caps what every turn re-reads. Claude Code's default on 1M-window
  models is about 967k. Measured across this repo's sessions in 2026-09,
  re-reading context was 71% of Opus orchestrator spend, and turns above 300k
  context were over half of it. Set it once; it matters more than model or
  effort.

Set model and effort with `/model` before starting a session. Rules of thumb:
spend on tier when the work is judgment-bound (design, brainstorming); spend on
effort when it is investigation-bound (review, debugging). Structure substitutes
for effort — a Superpowers workflow or a human in the loop supplies the breadth
and depth-checking the model would otherwise need effort budget for.

| Session type                                       | Model / effort       |
| -------------------------------------------------- | -------------------- |
| Brainstorming, high-stakes or ambiguous, freeform  | Fable, medium-high   |
| Brainstorming, high-stakes, via "Let's brainstorm" | Fable, low           |
| Brainstorming, routine stakes                      | Opus, high           |
| Plan execution / subagent-driven development       | Opus, high           |
| Quick questions, small fixes                       | Opus, high (default) |

Two settings to avoid: running the execution-phase session below `high` (the
orchestrator is the only quality gate over subagent work — under-effort there
compounds silently), and running it at `xhigh` (Opus at max deliberation tends
to redo the subagents' work instead of reviewing it).

Effort buys quality, not savings. Measured across the same sessions, output
tokens were 11-23% of spend at every effort level, so dropping to `medium` does
not lower cost in a useful way.

Subagent model choice is Claude's job, not yours. The root `CLAUDE.md`
_Subagents_ section governs it.

## Common Mistakes

**1. Skipping brainstorm because "it's simple."** Simple things are where
unexamined assumptions waste the most time. The brainstorm can be short — but it
must happen.

**2. Executing before the team reviews the spec.** The spec is where the team
aligns. Skipping review means building something nobody agreed to.

**3. Telling Claude "it's fine" when you don't understand.** If something
doesn't make sense, say so. Claude will explain or adjust. Rubber- stamping
approvals leads to bad designs.

**4. Not checking in during execution.** Claude runs the whole plan without
pausing. If you disappear for an hour, you might come back to a mess. Check in
every few tasks.

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
5        "Let's execute the plan" Plan execution              Completed code
6        (automatic)              Verify + PR                 PR URL
```
