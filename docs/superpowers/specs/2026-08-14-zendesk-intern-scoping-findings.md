# Fall Zendesk ticket analysis — data-team intern scoping

Refs #4862

**Status:** draft for review by Laszlo de Simon and Jabari Bradley **Author:**
Anthony Walters (analysis assisted by Claude Code) **Date:** 2026-08-14

## Why you are reading this

We are scoping whether an intern could absorb a meaningful share of the fall
data-team ticket queue, and if so, which parts. This document is the analysis
that would inform the runbook — **not** the runbook itself, and not a decision
that has been made.

Every claim below links to real tickets so you can check my reading. Where I am
guessing about intent or policy, I say so and ask.

**What I need from you:** the questions in
[What I need you to confirm or correct](#what-i-need-you-to-confirm-or-correct).
The data tells me what happened; it cannot tell me _why_ you made a given call,
and several conclusions hinge on that.

### A note on how ticket text is handled

Ticket bodies and your replies contain scholar names, student numbers, staff
emails, and phone numbers. None of that appears here — quotes are paraphrased or
redacted to `{DSO}` / `a scholar`, and only ticket IDs and URLs are reproduced.
Full text stayed on a local machine and was not committed.

## TL;DR

- Roughly **69% of your fall tickets are runbook-shaped work**, not analysis.
  That share has been stable for four straight seasons, so it is structural.
- A large slice of that is **not work you do** — it is work you _redirect_ to
  school ops or back to the requester. That reframes the intern role toward
  triage.
- **Ask type and platform together predict the path**; platform alone is a
  weaker signal than I first thought (see
  [correction](#a-correction-made-during-this-analysis)).
- **PowerSchool splits inside itself**: permission asks are yours (68%), roster
  asks are school ops' (26% yours). This is the most robust finding here.
- The DeansList access-level policy you already apply is real and repeated — but
  applied inconsistently, which is the strongest argument for writing it down.

## Scope and method

| Item          | Value                                                     |
| ------------- | --------------------------------------------------------- |
| Tickets       | 3,002                                                     |
| Window        | Aug 1 – Oct 31, 2022, 2023, 2024, 2025                    |
| Filter        | `assignee_id` is Laszlo de Simon or Jabari Bradley        |
| Source        | `kipptaf_zendesk` BigQuery views (not the Zendesk API)    |
| Not scoreable | 143 (54 Zendesk-redacted, 73 routing notes, 16 too short) |
| Scored        | 2,859                                                     |

Every ticket body was read to build the type taxonomy; pattern rules then sized
each type; each ticket's first agent reply was pulled from `ticket_audits` to
determine how it was actually resolved.

### Three things that shaped the analysis

1. **Subjects are not usable.** They are generic ("DeansList", "PowerSchool
   access") and 48 are Zendesk-`scrubbed`. Request type only lives in the body.
   Examples: [333185](https://teamschools.zendesk.com/agent/tickets/333185),
   [333186](https://teamschools.zendesk.com/agent/tickets/333186),
   [333187](https://teamschools.zendesk.com/agent/tickets/333187).
1. **Reply history only exists for 2023-2025.** All 618 tickets from Aug-Oct
   2022 have zero rows in `ticket_audits`. Every "how was it resolved" number
   below covers **2,266 tickets**, not 3,002.
1. **"Intern-eligible" initially conflated two different jobs.** The first pass
   counted any manual-execution-shaped _request_. Reading the replies showed
   much of it is a scripted redirect, not execution.

### A correction made during this analysis

An earlier draft claimed `SchoolMint Grow` / `Whetstone` was executed in-house
100% of the time (9 for 9) and used it as the clean example of "no SIS
integration means the data team must do it." **That was an artifact and has been
removed.**

Cause: a standard onboarding reply — _"your account should be ready for access…
make sure you are logged into Okta"_ — enumerates every system. It was used on
**21 tickets**, and **8 of those named SchoolMint/Whetstone** in the
enumeration. The platform tagger read replies before requests and took the first
match, so those 8 were misfiled under Grow/Whetstone.

The tagger now reads the **request** first and ignores any reply naming three or
more platforms. Effects of the fix:

- Grow/Whetstone drops to 22 tickets with 2 executions — too few to rate.
- `Clever` fell from 45% to 24% owned; `Google Classroom` from 29% to 19%.
- `iReady` rose from 44% to 50%, which **weakened** my original claim that
  blended-learning platforms are uniformly deflected.
- The PowerSchool internal split got slightly **stronger** (67/24 → 68/26).

I am flagging this because it is the kind of error that is invisible in a
summary, and because it shows the middle of the platform table is softer than it
looked.

## Finding 1 — volume is large and structurally stable

| Season | Runbook-shaped | Analyst | Runbook share |
| ------ | -------------- | ------- | ------------- |
| 2022   | 423            | 99      | 81%           |
| 2023   | 573            | 174     | 77%           |
| 2024   | 440            | 134     | 77%           |
| 2025   | 526            | 148     | 78%           |

Four seasons within four points of each other. Not a backlog artifact.

- **August is the crunch** — 836 of 1,962 runbook-shaped tickets (43%) land in
  August, 698 in September, 428 in October.
- Runbook-shaped tickets close in **11.7 business hours median**; analyst
  tickets take **27.1**.
- 75% resolve in two replies or fewer; 86% are never reassigned.

## Finding 2 — tickets resolve three ways, not two

Of the 1,120 tickets whose first reply was classifiable (excluding 82 duplicate
close-outs):

| Path                                            | Count | Share |
| ----------------------------------------------- | ----- | ----- |
| Data team executed                              | 434   | 39%   |
| Deflected — school ops, self-serve, or self-fix | 323   | 29%   |
| Bounced back for clarification                  | 288   | 26%   |
| Vendor escalation or internal routing           | 75    | 7%    |

Deflection splits into **school ops / DSO** (77), **requester self-serve with a
guide** (187), and **self-fix** — clear cache, re-login, wrong Clever role (59).

## Finding 3 — two clear poles, and a soft middle

"Owns" = of tickets that got a decision, the share executed rather than
deflected.

| Platform                         | Tickets | Executed | Deflected | → ops | → self | Owns    |
| -------------------------------- | ------- | -------- | --------- | ----- | ------ | ------- |
| DeansList                        | 690     | 175      | 99        | 17    | 82     | 64%     |
| PowerSchool                      | 427     | 106      | 82        | 36    | 46     | 56%     |
| Google Workspace (student accts) | 50      | 11       | 9         | 0     | 9      | 55%     |
| Illuminate                       | 139     | 22       | 19        | 2     | 17     | 54%     |
| iReady                           | 190     | 26       | 26        | 6     | 20     | 50%     |
| Amplify / mClass / DIBELS        | 193     | 24       | 30        | 7     | 23     | 44%     |
| Other curriculum apps            | 102     | 11       | 15        | 4     | 11     | 42%     |
| Clever                           | 76      | 4        | 13        | 2     | 11     | 24%     |
| Google Classroom                 | 57      | 3        | 13        | 0     | 13     | 19%     |
| SchoolMint Grow / Whetstone      | 22      | 2        | 0         | 0     | 0      | too few |

Read this as **two poles and a band**, not a gradient:

- **Owned pole:** `DeansList` at 64%, and it is the single biggest platform in
  the queue.
- **Deflected pole:** `Clever` at 24% and `Google Classroom` at 19% — these are
  almost never yours, because the fix is upstream or the requester already has
  the rights.
- **The middle (42-56%) is not differentiated by platform.** PowerSchool, Google
  Workspace, Illuminate, iReady, and Amplify all sit within 14 points. **For
  these, the ask type decides, not the platform.**

Google Classroom, almost always answered with a how-to:
[329011](https://teamschools.zendesk.com/agent/tickets/329011),
[329115](https://teamschools.zendesk.com/agent/tickets/329115),
[330126](https://teamschools.zendesk.com/agent/tickets/330126),
[380513](https://teamschools.zendesk.com/agent/tickets/380513),
[381179](https://teamschools.zendesk.com/agent/tickets/381179),
[425901](https://teamschools.zendesk.com/agent/tickets/425901).

Clever, deflected or self-fixed — note the last one states outright that any
staff member at the school can reset a student password:
[333870](https://teamschools.zendesk.com/agent/tickets/333870),
[427034](https://teamschools.zendesk.com/agent/tickets/427034),
[428870](https://teamschools.zendesk.com/agent/tickets/428870).

The mechanism appears in your own replies — app access follows from the
PowerSchool gradebook assignment, so the fix belongs upstream:
[329140](https://teamschools.zendesk.com/agent/tickets/329140),
[338108](https://teamschools.zendesk.com/agent/tickets/338108),
[378483](https://teamschools.zendesk.com/agent/tickets/378483),
[380591](https://teamschools.zendesk.com/agent/tickets/380591),
[380661](https://teamschools.zendesk.com/agent/tickets/380661),
[381001](https://teamschools.zendesk.com/agent/tickets/381001).

## Finding 4 — PowerSchool splits inside itself

The strongest and most actionable result. Same platform, opposite answers:

| Ask type                                              | Tickets | Executed | → ops | → self | Owns |
| ----------------------------------------------------- | ------- | -------- | ----- | ------ | ---- |
| Permission / account (admin vs teacher, SSO, campus)  | 216     | 75       | 14    | 21     | 68%  |
| Roster / section (homeroom, section, lead/co-teacher) | 70      | 8        | 15    | 8      | 26%  |

A 2.6x difference within one platform. Proposed rule: **PowerSchool permissions
are the data team's; PowerSchool rosters are school ops'.**

Permission asks you executed:
[322805](https://teamschools.zendesk.com/agent/tickets/322805),
[324984](https://teamschools.zendesk.com/agent/tickets/324984),
[325915](https://teamschools.zendesk.com/agent/tickets/325915),
[326989](https://teamschools.zendesk.com/agent/tickets/326989),
[327852](https://teamschools.zendesk.com/agent/tickets/327852),
[328506](https://teamschools.zendesk.com/agent/tickets/328506),
[381084](https://teamschools.zendesk.com/agent/tickets/381084),
[430238](https://teamschools.zendesk.com/agent/tickets/430238).

Roster asks you sent to school ops:
[331464](https://teamschools.zendesk.com/agent/tickets/331464),
[331584](https://teamschools.zendesk.com/agent/tickets/331584),
[332110](https://teamschools.zendesk.com/agent/tickets/332110),
[332517](https://teamschools.zendesk.com/agent/tickets/332517),
[332547](https://teamschools.zendesk.com/agent/tickets/332547),
[332976](https://teamschools.zendesk.com/agent/tickets/332976),
[334357](https://teamschools.zendesk.com/agent/tickets/334357),
[334868](https://teamschools.zendesk.com/agent/tickets/334868).

This is also visible in what the executed work consists of:

- **DeansList (175 executions)** — 65 account grants, 15 SSO, 13 campus
  reassignments, 11 permission tiers, 6 list configs. A **provisioning shop**.
- **PowerSchool (106 executions)** — 40 permission tiers, 14 account grants, 13
  SSO, and only **7** roster fixes. A **permissions shop**.

## Finding 5 — the two deflection scripts are platform-specific

They are not interchangeable, which matters for a runbook.

| Script             | Total | Concentrates in                                           |
| ------------------ | ----- | --------------------------------------------------------- |
| "Go to your DSO"   | 77    | PowerSchool 36 (47%), DeansList 17 (22%), Amplify 7 (9%)  |
| "Here's the guide" | 246   | DeansList 82 (33%), PowerSchool 46 (19%), Amplify 23 (9%) |

"Go to your DSO" is largely a PowerSchool-roster answer. "Here's the guide" is
largely a DeansList answer.

## Finding 6 — the DeansList access-level policy is real but inconsistent

A recurring reply appears **21 times**, with a consistent four-part shape:
thanks, "user access levels in DeansList are handled at the school level by the
DSO/Ops teams", loop in the named `{DSO}`, link the guide, close.

Examples: [326346](https://teamschools.zendesk.com/agent/tickets/326346),
[328614](https://teamschools.zendesk.com/agent/tickets/328614),
[328762](https://teamschools.zendesk.com/agent/tickets/328762),
[378552](https://teamschools.zendesk.com/agent/tickets/378552),
[380731](https://teamschools.zendesk.com/agent/tickets/380731),
[382560](https://teamschools.zendesk.com/agent/tickets/382560),
[382810](https://teamschools.zendesk.com/agent/tickets/382810),
[389257](https://teamschools.zendesk.com/agent/tickets/389257).

**But on permission-tier tickets the work was still done in-house 55 times out
of 108.** Examples where the access level was changed rather than redirected:
[329654](https://teamschools.zendesk.com/agent/tickets/329654),
[337214](https://teamschools.zendesk.com/agent/tickets/337214),
[338161](https://teamschools.zendesk.com/agent/tickets/338161),
[377354](https://teamschools.zendesk.com/agent/tickets/377354),
[427555](https://teamschools.zendesk.com/agent/tickets/427555),
[427683](https://teamschools.zendesk.com/agent/tickets/427683).

One ticket captures the handoff mid-stream — accounts were updated, then the
requester was asked to send this type of request to the ops lead going forward:
[332613](https://teamschools.zendesk.com/agent/tickets/332613).

School-ops deflection ran 9% / 5% / 9% across 2023 / 2024 / 2025, so this is a
long-standing habit rather than new policy.

**This is my most important question for you.** Is the 55 a deliberate judgment
call (DSO unavailable, urgent, requester already tried), or is it drift?

## Finding 7 — the Clever-fed platforms are high volume, low yield

`Amplify` + `iReady` + `Clever` + `Google Classroom` produced **516 tickets and
57 executions — an 11% yield**. `DeansList` + `Illuminate` produced **829
tickets and 197 executions — 24%**, more than double.

Note the nuance the correction exposed: this holds **in aggregate yield**, but
not platform-by-platform. iReady's _decided_ tickets split evenly (50% owned).
The pattern is about how much of the volume is noise, not about who owns a given
iReady ticket.

The clearest illustration is an October 2024 cluster where iReady vanished from
many teachers' Clever pages within days — near-identical tickets:
[386711](https://teamschools.zendesk.com/agent/tickets/386711),
[386719](https://teamschools.zendesk.com/agent/tickets/386719),
[386727](https://teamschools.zendesk.com/agent/tickets/386727),
[386735](https://teamschools.zendesk.com/agent/tickets/386735),
[386742](https://teamschools.zendesk.com/agent/tickets/386742),
[386786](https://teamschools.zendesk.com/agent/tickets/386786),
[386804](https://teamschools.zendesk.com/agent/tickets/386804),
[386805](https://teamschools.zendesk.com/agent/tickets/386805).

The recurring DIBELS/mClass "stuck in demo mode" issue has the same character —
one known fix, repeated every August:
[325544](https://teamschools.zendesk.com/agent/tickets/325544),
[326887](https://teamschools.zendesk.com/agent/tickets/326887),
[328537](https://teamschools.zendesk.com/agent/tickets/328537),
[380630](https://teamschools.zendesk.com/agent/tickets/380630),
[380927](https://teamschools.zendesk.com/agent/tickets/380927),
[381634](https://teamschools.zendesk.com/agent/tickets/381634).

The same argument applies to the 234 staff SSO/login tickets — a chunk recur
every August, and some appear to be new hires whose Okta app assignments were
not provisioned from the HR record.

**Recommendation:** look at root cause here before staffing it. Adding a person
to close these faster treats the symptom.

## Finding 8 — a quarter of first replies ask for clarification

**288 tickets (26% of classifiable replies)** open by asking for the school, the
student, the app, or a screenshot before any work can start:
[323675](https://teamschools.zendesk.com/agent/tickets/323675),
[324470](https://teamschools.zendesk.com/agent/tickets/324470),
[324870](https://teamschools.zendesk.com/agent/tickets/324870),
[328166](https://teamschools.zendesk.com/agent/tickets/328166),
[328230](https://teamschools.zendesk.com/agent/tickets/328230),
[334393](https://teamschools.zendesk.com/agent/tickets/334393),
[437184](https://teamschools.zendesk.com/agent/tickets/437184).

An intern with a required-fields checklist could absorb this, but the better fix
is upstream: make the intake form require school + system + affected person
before submission. That is a config change, not a hire.

## Full ticket-type inventory

Counts are four-season totals (Aug-Oct 2022-2025), then per-season average.

### Provisioning and access — 1,115 (≈279/season)

| Type                                                   | Total | /season |
| ------------------------------------------------------ | ----- | ------- |
| Staff SSO / login failure                              | 234   | 59      |
| Permission-tier escalation                             | 208   | 52      |
| Staff app access grant — DeansList                     | 196   | 49      |
| Staff app access grant — assessment / blended-learning | 167   | 42      |
| Staff campus / site reassignment                       | 93    | 23      |
| Staff app access grant — PowerSchool                   | 87    | 22      |
| Staff access removal / deprovision                     | 43    | 11      |
| Staff app access grant — Illuminate                    | 38    | 10      |
| Add missing app to Clever portal                       | 34    | 9       |
| Staff name / email identity fix                        | 15    | 4       |

Net-new DeansList provisioning, executed in-house:
[322938](https://teamschools.zendesk.com/agent/tickets/322938),
[323386](https://teamschools.zendesk.com/agent/tickets/323386),
[324134](https://teamschools.zendesk.com/agent/tickets/324134),
[324945](https://teamschools.zendesk.com/agent/tickets/324945),
[325922](https://teamschools.zendesk.com/agent/tickets/325922),
[326000](https://teamschools.zendesk.com/agent/tickets/326000). Campus
reassignment, also executed in-house (only 12% deflected):
[324024](https://teamschools.zendesk.com/agent/tickets/324024),
[324065](https://teamschools.zendesk.com/agent/tickets/324065),
[324220](https://teamschools.zendesk.com/agent/tickets/324220),
[324947](https://teamschools.zendesk.com/agent/tickets/324947),
[329099](https://teamschools.zendesk.com/agent/tickets/329099),
[331499](https://teamschools.zendesk.com/agent/tickets/331499).

### Roster edits — 393 (≈98/season)

| Type                                          | Total | /season |
| --------------------------------------------- | ----- | ------- |
| PowerSchool student section / homeroom fix    | 123   | 31      |
| App roster add / remove, single student       | 90    | 23      |
| Teacher-to-class assignment in an app         | 82    | 21      |
| Google Classroom setup / ownership / roster   | 57    | 14      |
| Grow / Whetstone caseload and manager mapping | 23    | 6       |
| DIBELS / mClass demo-mode fix                 | 11    | 3       |
| PowerSchool teacher-to-section assignment     | 7     | 2       |

App-roster edits with no SIS integration behind them:
[327430](https://teamschools.zendesk.com/agent/tickets/327430),
[328582](https://teamschools.zendesk.com/agent/tickets/328582),
[329077](https://teamschools.zendesk.com/agent/tickets/329077),
[339589](https://teamschools.zendesk.com/agent/tickets/339589),
[386754](https://teamschools.zendesk.com/agent/tickets/386754). Genuine
Grow/Whetstone caseload and manager fixes:
[328189](https://teamschools.zendesk.com/agent/tickets/328189),
[330036](https://teamschools.zendesk.com/agent/tickets/330036),
[334527](https://teamschools.zendesk.com/agent/tickets/334527),
[379066](https://teamschools.zendesk.com/agent/tickets/379066),
[379434](https://teamschools.zendesk.com/agent/tickets/379434).

### Platform configuration — 190 (≈48/season)

| Type                                         | Total | /season |
| -------------------------------------------- | ----- | ------- |
| Notification / referral routing              | 60    | 15      |
| DeansList report or list enabled on a campus | 56    | 14      |
| DeansList picklist / button config           | 34    | 9       |
| DeansList mobile app / device pairing        | 14    | 4       |
| Out-of-district attendance coding            | 13    | 3       |
| Calendar / non-attendance-day correction     | 7     | 2       |
| Letter or report header fix                  | 6     | 2       |

Picklist and button config — highly templated, often copying another campus:
[276590](https://teamschools.zendesk.com/agent/tickets/276590),
[276709](https://teamschools.zendesk.com/agent/tickets/276709),
[278442](https://teamschools.zendesk.com/agent/tickets/278442),
[279436](https://teamschools.zendesk.com/agent/tickets/279436),
[286794](https://teamschools.zendesk.com/agent/tickets/286794),
[432808](https://teamschools.zendesk.com/agent/tickets/432808). Notification
routing: [277127](https://teamschools.zendesk.com/agent/tickets/277127),
[279145](https://teamschools.zendesk.com/agent/tickets/279145),
[281344](https://teamschools.zendesk.com/agent/tickets/281344),
[281844](https://teamschools.zendesk.com/agent/tickets/281844).

### Student accounts — 141 (≈35/season)

| Type                                      | Total | /season |
| ----------------------------------------- | ----- | ------- |
| Student password reset / disabled account | 111   | 28      |
| New student with no login provisioned     | 30    | 8       |

40% of these were deflected, and at least one reply states that all teachers can
reset student Google accounts themselves:
[327310](https://teamschools.zendesk.com/agent/tickets/327310),
[328104](https://teamschools.zendesk.com/agent/tickets/328104),
[333670](https://teamschools.zendesk.com/agent/tickets/333670),
[380956](https://teamschools.zendesk.com/agent/tickets/380956),
[427251](https://teamschools.zendesk.com/agent/tickets/427251). If that is
right, this is a training and guide problem more than an execution problem.

### Records and surveys — 62 (≈16/season)

| Type                        | Total | /season |
| --------------------------- | ----- | ------- |
| Student records pull        | 45    | 11      |
| Survey personal-link resend | 17    | 4       |

Records pulls send student records to a requester and need analyst sign-off, not
intern discretion:
[274199](https://teamschools.zendesk.com/agent/tickets/274199),
[275034](https://teamschools.zendesk.com/agent/tickets/275034),
[278149](https://teamschools.zendesk.com/agent/tickets/278149),
[279740](https://teamschools.zendesk.com/agent/tickets/279740),
[282863](https://teamschools.zendesk.com/agent/tickets/282863). Survey resends,
trivially scripted:
[337882](https://teamschools.zendesk.com/agent/tickets/337882),
[337910](https://teamschools.zendesk.com/agent/tickets/337910),
[338111](https://teamschools.zendesk.com/agent/tickets/338111),
[338282](https://teamschools.zendesk.com/agent/tickets/338282).

### Family-facing — 61 (≈15/season)

| Type                                    | Total | /season |
| --------------------------------------- | ----- | ------- |
| Family portal account help              | 39    | 10      |
| Family portal signup / validation codes | 11    | 3       |
| Family comms language change            | 11    | 3       |

### Analyst-only — 555 (≈139/season), do not route to an intern

| Category                             | Total |
| ------------------------------------ | ----- |
| In-app function broken, needs triage | 160   |
| Grades / report-card logic           | 82    |
| Cross-system data discrepancy        | 74    |
| Tableau / dashboard issue            | 72    |
| Integration / sync failure           | 62    |
| New vendor / platform onboarding     | 24    |
| New list / logic / automation build  | 23    |
| State / compliance reporting         | 20    |
| Platform-wide outage                 | 19    |
| Duplicate student record / merge     | 15    |
| School-store / points engine         | 4     |

Vendor escalations, for reference — these end up with DeansList or Amplify
support, not with us:
[332693](https://teamschools.zendesk.com/agent/tickets/332693),
[334204](https://teamschools.zendesk.com/agent/tickets/334204),
[335521](https://teamschools.zendesk.com/agent/tickets/335521),
[376944](https://teamschools.zendesk.com/agent/tickets/376944).

## Proposed intern scope

Two jobs with very different risk profiles. Recommendation is to start with the
second only.

### Job 1 — execute (gate this)

DeansList, Illuminate, and Google Workspace student accounts: **208 of 434
executions (48%)**, all on platforms with self-contained admin UIs where a
mistake is reversible in-app. Requires production write access.

Explicitly **not** PowerSchool roster writes — those belong to school ops
anyway, which conveniently removes the riskiest action from the intern's plate.
A dropped section or changed enrollment date corrupts attendance and ADA
downstream.

### Job 2 — triage and scripted redirect (start here)

Clever, Google Classroom, Amplify, and PowerSchool roster asks. Apply the ask-
type test, send the matching template, loop in the right DSO, close.

**Needs zero system access**, so it is safe on day one, and it directly
addresses the inconsistency in Finding 6.

### Consequence for the runbook structure

I had planned to structure the runbook purely by platform. The correction above
changes that: platform works as the **navigation** (you know it immediately),
but because the middle of the table is undifferentiated, **each platform section
has to branch on ask type** — and for PowerSchool that branch is the whole game.

## What I need you to confirm or correct

1. **Finding 6, the 55 in-house permission changes.** Deliberate judgment (DSO
   unavailable, urgent, requester already tried) or drift? This decides whether
   the runbook says "always redirect" or "redirect unless X".
1. **Is the ask-type-over-platform read in Findings 3 and 4 how you actually
   think about it**, or is the pattern driven by something else — who was on
   duty, how the ticket was worded, which region it came from?
1. **PowerSchool permissions vs rosters** — a real ownership boundary, or does
   it vary by school depending on DSO capability?
1. **Which DSOs and ops leads are actually equipped to take these?** The
   redirect only works if the named person can do it. Uniform across Newark,
   Camden, Miami, and Paterson, or school by school?
1. **Student password resets** — can teachers and ops staff genuinely self-serve
   these? If yes, 111 tickets are a guide problem.
1. **Anything in the analyst-only list you would hand to an intern**, or
   anything in the runbook-shaped list you would never hand over?
1. **Records pulls** — what is your sign-off practice before student records
   leave in a ticket reply?

## Confidence and known gaps

**High confidence:** the type inventory, the PowerSchool permission/roster
split, and the DeansList access-level pattern. Every ticket body was read, and
none of these three depend on the platform tagger.

**Moderate confidence:** the platform ownership table. Runbook-vs-analyst
assignment tested ~87% accurate on a hand-scored random sample of 40. Individual
type boundaries bleed roughly 30%, almost entirely between neighbouring
runbook-shaped types rather than across the runbook/analyst line. Treat any
single row as ±25-30%.

**Low confidence:** anything distinguishing platforms inside the 42-56% band.
The correction above moved several of those by 5-20 points.

Every ticket cited in this document was spot-checked against its actual request
and reply. Four citations that did not support the claim they were attached to
were removed rather than reworded. If you open a link and it does not say what I
claim it says, that is a real error and I want to know.

**Known gaps:**

- **45% of replies did not match the pattern set** and are uncounted in Findings
  2-7. Sampling shows they skew toward "executed", so the ownership percentages
  are **floors, not ceilings**.
- **No 2022 reply data** — `ticket_audits` retains nothing that far back.
- **"Closed by" means current assignee**, not whoever set status to solved.
- **First reply only.** Some first replies are internal routing notes, which
  land in the unmatched bucket.
- **244 tickets (11%) have no identifiable platform** in request or reply.
- Platform is a single primary tag. Only 46 tickets name both DeansList and
  PowerSchool explicitly, so those two are not badly cross-contaminated; the
  PowerSchool split in Finding 4 is immune since both halves are one platform.

## Reproducing this

Cohort definition, in `kipptaf_zendesk`:

```sql
select t.id
from `teamster-332318.kipptaf_zendesk.tickets` as t
where t.assignee_id in (187174232, 418896194213)
  and extract(month from t.created_at) between 8 and 10
  and t.created_at between '2022-08-01' and '2025-11-01'
```

Agent replies come from `ticket_audits`, unnesting `events` and filtering
`$.type = 'Comment'` with `$.public = true` and `$.author_id` in the two agent
IDs. `$.plain_body` carries the reply text.

Classification scripts ran locally and are not committed, because they read
ticket bodies containing PII. They can be regenerated from the query above plus
the type definitions in this document.

## Next step

Once reviewed, the runbook gets written with platform as the navigation and ask
type as the branch inside each platform.
