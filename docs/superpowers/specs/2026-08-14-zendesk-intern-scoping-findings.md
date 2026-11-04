# Fall Zendesk ticket analysis — data-team intern scoping

Refs #4862

**Status:** revised 2026-08-14 with Jabari Bradley's review. Laszlo de Simon's
review is not expected this cycle, so the findings proceed without it — see
[Review status](#review-status). **Author:** Anthony Walters (analysis assisted
by Claude Code)

> **Revision note.** Jabari answered questions 1-5. His answers are folded into
> the findings they affect, and one of them produced a new finding
> ([Finding 9](#finding-9--requester-affiliation-is-the-first-gate)) that
> outranks most of what was here before. Two questions were never answered and
> Laszlo's review is not coming, so the
> [runbook](2026-08-14-zendesk-triage-runbook.md) was written conservatively on
> those branches rather than waiting.

## Why you are reading this

We are scoping whether an intern could absorb a meaningful share of the fall
data-team ticket queue, and if so, which parts. This document is the analysis
that would inform the runbook — **not** the runbook itself, and not a decision
that has been made.

Every claim below links to real tickets so you can check my reading. Where I am
guessing about intent or policy, I say so and ask.

**What I need from you:** the still-open items under
[Review status](#review-status). The data tells me what happened; it cannot tell
me _why_ a given call was made, and several conclusions hinge on that.

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
- **Who is asking decides more than what they are asking about.** Regional (Room
  9/10/11) requesters are handled in house essentially without exception;
  school-based requesters are supposed to be redirected and mostly are not. This
  is the sharpest rule in the data and it came from Jabari, not from me — see
  [Finding 9](#finding-9--requester-affiliation-is-the-first-gate).
- **PowerSchool splits inside itself**: permission asks are yours (68%), roster
  asks are school ops' (26% yours). Jabari confirms permissions should stay 100%
  data-team; rosters are capability-dependent, not a clean boundary.
- **DeansList ownership is a guide gap, not a policy boundary.** You own the
  config work because there is nothing to deflect it with. That reorders the
  recommendations.
- **Ask type and platform together predict the path**; platform alone is a
  weaker signal than I first thought (see
  [correction](#a-correction-made-during-this-analysis)).

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

### What Jabari says is actually driving this

> Most DeansList "owns" are due to the requester's lack of ability to update
> configs in DL. Not enough training, or we don't have guides to deflect the
> config tickets like "need new list."

So the 64% is **not** a judgment that DeansList belongs to the data team. It is
the absence of anything to redirect with. That matters because it makes the
number movable: `DeansList report / list enable` (56) plus
`DeansList picklist / button config` (34) is **90 tickets that are deflected
essentially never** — 2 to ops and 4 to self-serve across four seasons. Examples
handled in house:
[324947](https://teamschools.zendesk.com/agent/tickets/324947),
[324964](https://teamschools.zendesk.com/agent/tickets/324964),
[327649](https://teamschools.zendesk.com/agent/tickets/327649),
[328369](https://teamschools.zendesk.com/agent/tickets/328369),
[330698](https://teamschools.zendesk.com/agent/tickets/330698),
[331563](https://teamschools.zendesk.com/agent/tickets/331563).

Finding 8 shows guides already work: when self-serve deflection tripled in 2024,
in-house share fell with it. Writing the missing config guides converts
execute-work into deflect-work permanently.

## Finding 4 — PowerSchool splits inside itself

The strongest and most actionable result. Same platform, opposite answers:

| Ask type                                              | Tickets | Executed | → ops | → self | Owns |
| ----------------------------------------------------- | ------- | -------- | ----- | ------ | ---- |
| Permission / account (admin vs teacher, SSO, campus)  | 216     | 75       | 14    | 21     | 68%  |
| Roster / section (homeroom, section, lead/co-teacher) | 70      | 8        | 15    | 8      | 26%  |

A 2.6x difference within one platform. Jabari confirms the permission half as
policy and complicates the roster half:

> Permissions = We own 100% and should stay that way. Rosters = Depends on
> capability of DSO... sometimes a quick Zoom call is necessary for data
> accuracy, leads to less errors.

Three consequences:

1. **Permissions are settled** — data team owns them, and the runbook should say
   so flatly rather than describing an observed tendency.
1. **Rosters are not a rule, they are a capability question.** A blanket "send
   rosters to ops" would be wrong. On which DSOs can take them, Jabari's answer
   was that it is "really school by school, some DSOs are vets, some are rookies
   going into this year. But even the vets need support on rosters."
1. **A synchronous call is sometimes the correct resolution**, not a failure to
   deflect. I did not model this path at all, so it is invisible in every
   percentage in this document. A runbook should permit it explicitly for
   accuracy-critical roster work.

Also worth flagging: more guides and a scheduling portal land in 26-27, which
changes the baseline. Anything written for the roster branch has a known shelf
life.

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

### Answered

Jabari's answer: "Some drift, some judgement."

> If the requester is from room 9/10, I'll handle it. School based requesters
> should always be sent to ops with a guide. Ops should know how to do it 100%
> of the time.

That names a variable this analysis had not modelled — **who is asking** — and
it turns out to be the strongest predictor in the dataset. It gets its own
finding below.

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

## Finding 9 — requester affiliation is the first gate

This finding exists because Jabari named the rule; I then tested it against all
3,002 tickets. Requester affiliation comes from `home_work_location_name` on the
staff roster — Room 9 / 10 / 11 are the regional office, everything named
`KIPP <school>` is school-based.

Cohort mix: **67% school-based, 26% regional, 7% unknown.**

### The regional half of the rule is followed without exception

| Ask type                      | Requester    | Decided | In house | → ops | → self |
| ----------------------------- | ------------ | ------- | -------- | ----- | ------ |
| Permission-tier, all systems  | regional     | 21      | 16 (76%) | **0** | 5      |
| Permission-tier, all systems  | school-based | 60      | 36 (60%) | 10    | 14     |
| DeansList permission + access | regional     | 53      | 46 (87%) | **0** | 7      |
| DeansList permission + access | school-based | 104     | 68 (65%) | 11    | 25     |
| PowerSchool rosters           | regional     | 7       | 5 (71%)  | **0** | 2      |
| PowerSchool rosters           | school-based | 32      | 9 (28%)  | 17    | 6      |

A regional requester has **never** been redirected to school ops — zero across
every cut, and only 4 instances across all of Tier A. That is not drift; it is a
rule applied consistently. Examples handled in house:
[324213](https://teamschools.zendesk.com/agent/tickets/324213),
[326426](https://teamschools.zendesk.com/agent/tickets/326426),
[327227](https://teamschools.zendesk.com/agent/tickets/327227),
[327955](https://teamschools.zendesk.com/agent/tickets/327955).

### The school-based half is followed about one time in seven

Jabari's standard is that school-based requesters should "always" be sent to
ops. On DeansList permission and access asks, 11 of 104 decided tickets were.
The other 68 were handled in house:
[322805](https://teamschools.zendesk.com/agent/tickets/322805),
[322938](https://teamschools.zendesk.com/agent/tickets/322938),
[324134](https://teamschools.zendesk.com/agent/tickets/324134),
[324945](https://teamschools.zendesk.com/agent/tickets/324945),
[324984](https://teamschools.zendesk.com/agent/tickets/324984),
[325793](https://teamschools.zendesk.com/agent/tickets/325793).

Correctly redirected, for contrast:
[326346](https://teamschools.zendesk.com/agent/tickets/326346),
[328614](https://teamschools.zendesk.com/agent/tickets/328614),
[330503](https://teamschools.zendesk.com/agent/tickets/330503),
[389257](https://teamschools.zendesk.com/agent/tickets/389257),
[425933](https://teamschools.zendesk.com/agent/tickets/425933).

**PowerSchool rosters are where the affiliation rule already works** — 28%
in-house for school-based versus 71% for regional, a 2.5x split, with 17 tickets
correctly routed to ops:
[330437](https://teamschools.zendesk.com/agent/tickets/330437),
[331464](https://teamschools.zendesk.com/agent/tickets/331464),
[331584](https://teamschools.zendesk.com/agent/tickets/331584),
[332110](https://teamschools.zendesk.com/agent/tickets/332110),
[332517](https://teamschools.zendesk.com/agent/tickets/332517),
[332976](https://teamschools.zendesk.com/agent/tickets/332976).

### The gap is closing, but through guides rather than handoffs

School-based permission and DeansList access asks:

| Season | Decided | In house | → ops | → self-serve |
| ------ | ------- | -------- | ----- | ------------ |
| 2023   | 30      | 22 (73%) | 4     | 4            |
| 2024   | 36      | 23 (64%) | 1     | **12**       |
| 2025   | 38      | 23 (61%) | 6     | 9            |

In-house share fell 73% to 61% over three seasons and nearly all of that went to
**self-serve guides**, not ops handoffs. This is the same conclusion Finding 3
reaches from the other direction: guides move volume, handoff requests mostly do
not.

### Why this reorders the runbook

For permission and access asks, affiliation is a **cheaper and more accurate
first question than platform or ask type**. Regional means do it. School-based
means guide plus DSO. The rule already exists and is already applied perfectly
on one side, so the runbook is closing one branch rather than introducing
policy.

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
[427251](https://teamschools.zendesk.com/agent/tickets/427251).

**Confirmed.** Teachers can reset student passwords and a help guide already
exists. So these 111 tickets are a guide-distribution problem, not execution
work — the guide does not need writing, it needs sending. Replies that already
do this: [328104](https://teamschools.zendesk.com/agent/tickets/328104),
[331554](https://teamschools.zendesk.com/agent/tickets/331554),
[333670](https://teamschools.zendesk.com/agent/tickets/333670),
[380846](https://teamschools.zendesk.com/agent/tickets/380846),
[381792](https://teamschools.zendesk.com/agent/tickets/381792). This moves the
whole type out of the execute column and into scripted redirect.

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

Revised after Jabari's review. Three pieces of work, in the order I would hand
them over.

### First project — write the missing config guides (no system access)

Jabari's Finding 3 answer identifies the binding constraint: config tickets are
handled in house because there is nothing to deflect them with. That makes
**writing those guides the highest-leverage thing an intern could do**, ahead of
the role-permission matrix I proposed in the first draft.

Scope: `DeansList report / list enable` (56) and
`DeansList picklist / button config` (34) — 90 tickets over four seasons,
currently deflected 6 times total. The 2024 jump in self-serve deflection
(Finding 9) is the evidence that guides actually move volume.

This needs zero production access, it is reviewable before anything ships, and
it permanently converts execute-work into deflect-work rather than just
absorbing it faster.

### Second — triage and scripted redirect (still no system access)

Four streams, all resolved by sending something rather than doing something:

- **School-based permission and access asks** — apply the affiliation gate from
  Finding 9. Regional goes to an analyst; school-based gets the guide plus the
  named DSO. This is the branch that is currently followed one time in seven, so
  it is where a runbook changes behaviour most.
- **Student password resets** (111 tickets) — confirmed self-serve with an
  existing guide. Send the guide.
- **Clever, Google Classroom, Amplify** — 19-44% owned; the answer is almost
  always a redirect, a cache clear, or "the sync has not run yet."
- **PowerSchool roster asks** — but see the capability caveat below.

### Third — execute (gate on write access)

DeansList and Illuminate provisioning: net-new accounts, campus reassignment,
Clever app catalogue. Self-contained admin UIs where a mistake is reversible
in-app.

Smaller than the first draft claimed, because student password resets moved into
the redirect stream above.

Explicitly **not** PowerSchool roster writes. Those belong to school ops, and a
dropped section or changed enrollment date corrupts attendance and ADA
downstream.

### Two things the runbook must not do

**Do not write a blanket roster deflect.** Jabari: DSO capability is "really
school by school... even the vets need support on rosters." The roster branch
needs a per-school capability tier, and it should explicitly permit a short Zoom
call where accuracy matters — that is a legitimate resolution, not a failure to
deflect. It is also the branch with the shortest shelf life, since more guides
and a scheduling portal arrive in 26-27.

**Do not lead with platform.** For permission and access asks the cheapest
accurate first question is **who is asking** (Finding 9), then ask type, then
platform. Platform remains useful as navigation — you know it the moment you
open the ticket — but it is the weakest of the three predictors in the middle of
the table.

## Review status

### Answered by Jabari

1. **The 55 in-house permission changes** — "some drift, some judgement." Room
   9/10 requesters he handles; school-based should always go to ops with a
   guide. Folded into Finding 6 and expanded into
   [Finding 9](#finding-9--requester-affiliation-is-the-first-gate).
1. **What drives the DeansList ownership number** — a guide gap, not a policy
   boundary. Folded into Finding 3; it reorders the recommendations.
1. **PowerSchool permissions vs rosters** — permissions are 100% data-team "and
   should stay that way"; rosters depend on DSO capability. Folded into
   Finding 4.
1. **Which DSOs are equipped** — task-dependent and school by school; even
   experienced DSOs need roster support. Folded into Finding 4 and the scope
   section.
1. **Student password resets** — teachers can reset them and a guide exists.
   Folded into the Student accounts section; moves 111 tickets out of execution.

### Still open

1. **Anything in the analyst-only list you would hand to an intern**, or
   anything in the runbook-shaped list you would never hand over?
1. **Records pulls** — what is the sign-off practice before student records
   leave in a ticket reply? This one gates whether an intern touches that type
   at all.
1. **Laszlo's read on all of the above** — sought but not expected this cycle.
   Every number here pools both analysts, so a disagreement between them shows
   up as noise rather than as a difference. The affiliation rule in Finding 9 is
   Jabari's stated habit specifically, and may not be shared.

Rather than hold the work, the runbook treats each unanswered item as a
conservative default: records pulls require analyst sign-off, and the roster
branch offers a live handoff instead of asserting a boundary. Both are marked
provisional there, so a later answer changes one table rather than the whole
document.

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

**On Finding 9 specifically:** requester affiliation comes from
`home_work_location_name` on the staff roster, so the 7% of tickets whose
submitter does not resolve to a roster record are excluded. In-house shares are
computed on _decided_ tickets only, so the denominators there are small — 21
decided regional permission tickets, for example. The robust part is the
**absence**: zero regional-to-ops deflections across four independent cuts. The
percentage differences between regional and school-based are directional.

**One resolution path is missing entirely.** Jabari notes that a short Zoom call
is sometimes the right answer for roster accuracy. Nothing in this analysis can
see a call, so any ticket resolved that way is sitting in the unmatched 45% or
looks like an unexplained in-house resolution.

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

The runbook is written:
**[Fall ticket triage runbook](2026-08-14-zendesk-triage-runbook.md)**. Its
decision order is requester affiliation, then ask type, then platform — platform
serves as navigation rather than as the deciding variable.

Two things it depends on that do not exist yet:

1. **The DeansList config guides.** Until they exist, that branch instructs the
   reader to execute and log the request, so the backlog for writing them builds
   from real tickets.
1. **A per-school DSO capability picture.** The runbook asks for bounced
   redirects to be logged by school, which is the cheapest way to build it.
