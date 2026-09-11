# Fall ticket triage runbook — data team

Refs #4862

**Status:** draft v1, encodes Jabari Bradley's confirmed practice. Laszlo de
Simon has not reviewed it and is not expected to in this cycle, so anything
specific to his practice is unvalidated. **Companion:**
[findings](2026-08-14-zendesk-intern-scoping-findings.md), which carries the
evidence for every rule here.

> **Where this should live eventually.** This sits in `docs/superpowers/specs/`
> because it is still a working document. Once it has survived a live August, it
> should graduate to `docs/guides/` with a `mkdocs.yml` nav entry so it is
> reachable from the published site.

## What this is for

You are looking at a ticket in the data team queue and need to decide what to do
with it. Work through the steps in order. Each one ends in an action.

Three things to hold onto before you start:

1. **A ticket arriving does not mean you perform a task.** Roughly 39% of
   tickets get executed, 29% get redirected to whoever actually owns them, and
   26% cannot start because the request is incomplete. Redirecting well is the
   job, not an evasion of it.
1. **Order matters.** Who is asking is a better predictor than what they are
   asking about, and both beat which platform they named. Do not jump to the
   platform section first.
1. **When in doubt, do not guess — escalate.** The
   [hard stops](#hard-stops--never-do-these-without-sign-off) exist because some
   mistakes here are invisible for weeks and then surface as a reporting
   problem.

## Step 0 — is the request complete?

About a quarter of tickets cannot be worked as written. Check for all four
before going further:

| Needed             | Why                                             |
| ------------------ | ----------------------------------------------- |
| School or campus   | Almost every fix is scoped to one school        |
| System             | "It's not working" spans a dozen platforms      |
| Affected person    | Staff name, or scholar name plus student number |
| Expected vs actual | What they see, and what they expected to see    |

If any are missing, send [T1](#t1--request-more-detail) and stop. Do not guess
the school from the requester's signature — people submit on behalf of other
campuses.

## Step 1 — who is asking?

Look up the requester's work location. Regional staff sit at **Room 9, 10, or
11**; everyone else is at a named `KIPP {school}` site.

| Requester               | Default                                                                           |
| ----------------------- | --------------------------------------------------------------------------------- |
| Regional (Room 9/10/11) | **Data team handles it.** Do not redirect to school ops.                          |
| School-based            | **Redirect is the default** for permissions and config.                           |
| Parent or guardian      | Route to the school's ops team; never handle family-facing account work directly. |
| External or vendor      | Route to the analyst who owns that vendor relationship.                           |

The regional rule is absolute in four seasons of history — a regional requester
was never redirected to school ops. The school-based rule is the one that has
not been followed consistently, and it is the main behaviour this runbook is
meant to change.

**Why regional differs:** regional staff often need cross-school or cross-region
access that no single DSO can grant, so there is no one to redirect them to.

## Step 2 — what kind of ask is it?

| Ask type                                          | Owner                     | Confidence         |
| ------------------------------------------------- | ------------------------- | ------------------ |
| Permissions, accounts, access levels              | Data team                 | Confirmed          |
| Rosters, sections, homerooms                      | School ops — with caveats | Confirmed          |
| Platform config (lists, picklists, notifications) | Data team, for now        | Confirmed as a gap |
| Student account resets                            | Requester self-serves     | Confirmed          |
| Records and data pulls                            | Analyst sign-off required | **Unconfirmed**    |
| Discrepancies, dashboards, diagnosis              | Analyst                   | Confirmed          |

### Permissions and accounts — data team

Covers: who can log in, what they can see, which school they are attached to,
admin versus teacher tier, deprovisioning a departed teammate, and identity
fixes after a name or email change.

This is settled. PowerSchool permissions in particular are data-team-owned and
should stay that way.

The one split: for **school-based** requesters asking to change an access
_level_ in a system where the DSO has that ability — DeansList most often —
redirect with [T2](#t2--redirect-to-school-ops). For **regional** requesters,
execute.

### Rosters and sections — school ops, conditionally

Covers: which scholar sits in which homeroom or section, who the lead or
co-teacher is, grade-level corrections, dropping a leftover section.

School ops owns this, but three caveats are real:

- **DSO capability varies school by school.** Some are veterans, some are new
  this year, and even the veterans want support on rosters. A redirect to a DSO
  who cannot do it wastes a cycle and erodes trust in the redirect.
- **A short call is sometimes the correct answer.** Where accuracy matters,
  walking through it live with the DSO produces fewer errors than a written
  handoff. Offer it rather than treating it as a failure to deflect.
- **This branch has the shortest shelf life.** More guides and a scheduling
  portal arrive in 26-27, which will move the boundary.

Default to [T3](#t3--roster-handoff-with-a-live-option), which redirects and
offers a call in the same message.

### Platform config — data team, and log it

Covers: "we need a new list", adding a dropdown option or a button, notification
and referral routing, enabling a report on a campus, letter and report headers.

The data team handles these today **not because it owns them** but because there
is no guide to redirect with. So:

1. Execute the request.
1. **Log it** — one line in the config-guide backlog: system, what was asked,
   what you did, which campus. That backlog is what the guides get written from.

Once a guide exists for a given config type, that type moves to
[T4](#t4--self-serve-with-a-guide) and stops arriving.

### Student account resets — requester self-serves

Teachers can reset scholar passwords themselves and a help guide already exists.
Send [T4](#t4--self-serve-with-a-guide). This applies to the whole category:
password resets, disabled or suspended accounts, and badge or QR problems.

The exception is a genuinely **new scholar with no account provisioned at all**
— that is a provisioning ticket, and it belongs to the data team.

### Records and data pulls — sign-off required

Covers: attendance records, incident and behaviour logs, report cards and
transcripts for transferred or graduated scholars, records for audits.

**Do not send student records without an analyst signing off first.** The
practice for this has not been confirmed, so treat sign-off as mandatory until
it is. Hand off with [T6](#t6--analyst-handoff) and note who is asking, for
which scholar, and for what stated purpose.

### Discrepancies and diagnosis — analyst

If the ticket is "these two systems disagree", "the dashboard is wrong", "grades
are not calculating", or "the sync did not run", it is analyst work. Hand off
with [T6](#t6--analyst-handoff). Do not investigate — a partial diagnosis in the
ticket thread is worse than a clean handoff, because the analyst then has to
un-pick it.

## Step 3 — which platform?

Only reach this step once steps 1 and 2 point to the data team acting. This
tells you where the fix lives and what usually goes wrong.

### DeansList

Biggest single source of tickets. Has its own admin screens, so fixes are
direct.

| Ask                                     | Who                                              | Note                                     |
| --------------------------------------- | ------------------------------------------------ | ---------------------------------------- |
| Net-new account for a new teammate      | Data team                                        | Highest-volume execute task in the queue |
| Add a school to an existing account     | Data team                                        |                                          |
| Campus reassignment after a move        | Data team                                        | "My DeansList still says my old school"  |
| Change access level or admin tier       | School ops (school-based) / data team (regional) | DSOs have this ability                   |
| Remove a departed teammate              | Data team                                        | Also stops referral notifications        |
| Lists, reports, picklists, buttons      | Data team                                        | Log for the guide backlog                |
| Notification and referral routing       | Data team                                        | Log for the guide backlog                |
| Mobile app or device pairing, kiosk PIN | Data team                                        |                                          |

### PowerSchool

The SIS and the source of truth. The permission-versus-roster split is the whole
game here.

| Ask                                           | Who                     |
| --------------------------------------------- | ----------------------- |
| Admin versus teacher access, PowerTeacher Pro | Data team               |
| Adding a school to someone's access           | Data team               |
| Login and SSO failures                        | Data team               |
| Student section, homeroom, grade level        | School ops              |
| Lead or co-teacher assignment                 | School ops              |
| Dropping a leftover section                   | School ops              |
| Duplicate student records                     | **Analyst — hard stop** |

### Clever-fed apps — iReady, Amplify/mClass, Google Classroom

These receive rosters from PowerSchool through Clever. **The fix is usually not
in the app.** Before doing anything in the app itself, check in this order:

1. Is the person or scholar correct in **PowerSchool**? If not, that is a Step 2
   roster ask — redirect.
1. Has the **sync run** since the change? Observations and roster changes do not
   appear until the overnight refresh. If it is same-day, send
   [T5](#t5--upstream-or-sync-timing).
1. Is it a **cache or wrong-role** problem? Signing into Clever as Teacher
   rather than Staff hides apps. Send [T5](#t5--upstream-or-sync-timing).

Only after all three: the data team can add a missing app to a Clever page, or
add a teacher to a class in an app that does not derive that from PowerSchool.

**A recurring shape worth recognising:** several near-identical tickets arriving
within a day or two, all reporting the same app missing, usually means a
configuration change rather than individual account problems. Escalate the
cluster to an analyst rather than fixing accounts one at a time.

### Illuminate

Has its own account provisioning; data team owns it. Common asks: account
creation for a new teammate, campus reassignment after a move, adding a school
to someone's access. Roster problems inside Illuminate usually trace back to
PowerSchool — apply the Clever-fed checks above.

### Google Workspace — scholar accounts

Data team owns provisioning for genuinely new scholars. Everything else —
password resets, disabled accounts — is self-serve; send
[T4](#t4--self-serve-with-a-guide).

### SchoolMint Grow and Whetstone

Low volume in this queue, and it belongs to a different analyst. Coaching
caseload and manager-mapping tickets should be routed there rather than handled
here. Same for survey administration — Insight, Gallup, Survey HQ.

## Reply templates

Use `{braces}` for anything you fill in. Keep the requester's language for the
system name so it is obviously the same ticket.

### T1 — request more detail

```text
Hi {name} — happy to help with this. So I can get to the right place quickly,
could you send me:

- the school this is for
- the {system} screen you are on
- the {staff member / scholar name and student number} affected
- what you are seeing, and what you expected

Once I have those I will pick this straight up.
```

### T2 — redirect to school ops

```text
Hi {name} — thanks for flagging. User access levels in {system} are handled at
the school level by the DSO and ops team, so {DSO name} can make this change
directly and faster than we can.

Looping {DSO name} in here. Guide for reference: {guide link}.

Closing this out, but ping back if anything is still stuck.
```

### T3 — roster handoff with a live option

```text
Hi {name} — roster and section changes are made in PowerSchool by the school ops
team, so {DSO name} owns this one. Looping them in.

{DSO name} — if it is easier to walk through together, happy to jump on a quick
call; roster changes flow into attendance and ADA, so it is worth getting exactly
right the first time.
```

### T4 — self-serve with a guide

```text
Hi {name} — good news, this is something you can do directly and it should take
a minute: {guide link}.

Ping back if the guide does not cover what you are seeing.
```

### T5 — upstream or sync timing

```text
Hi {name} — thanks for the flag. {System} gets its rosters from PowerSchool
overnight, so a change made today will not show up until tomorrow morning.

{If applicable:} It is also worth signing into Clever as "Staff" rather than
"Teacher" — the app list differs between the two.

Give it until tomorrow and ping back if it still looks wrong.
```

### T6 — analyst handoff

```text
Hi {name} — thanks for this. Passing it to {analyst} to look at properly, since
{it involves student records that need sign-off before anything goes out / this
is a data question rather than an access one}.

{Analyst} — context: {one line, no diagnosis}.
```

## Hard stops — never do these without sign-off

1. **PowerSchool roster or enrollment writes.** A dropped section or a changed
   enrollment date propagates into attendance and ADA, where it becomes a
   reporting problem nobody traces back to a ticket.
1. **Sending student records out of a ticket.** Analyst sign-off first, every
   time, until the practice is confirmed.
1. **Merging duplicate student records.** Identity resolution — analyst only.
1. **Anything touching grades, report-card logic, or gradebook weighting.**
1. **Bulk changes.** If the fix touches more than a handful of people, stop and
   escalate; a cluster usually means an upstream cause.

## What is provisional

Behave conservatively where this list applies, and flag cases that would settle
them.

| Item                                                    | Status               |
| ------------------------------------------------------- | -------------------- |
| Records-pull sign-off practice                          | Never confirmed      |
| Whether any analyst-only category could be handed over  | Never confirmed      |
| Exactly where the roster boundary sits per school       | Capability-dependent |
| Laszlo's practice, and whether it differs from Jabari's | Unreviewed           |
| Anything about the 26-27 scheduling portal              | Not yet in effect    |

The underlying analysis pools both analysts, so a difference in how they work
currently reads as noise rather than as a disagreement. If you hit a case where
this runbook and an analyst's instruction conflict, **the analyst wins** — and
that conflict is worth writing down, because it is exactly what would improve
this document.

## Keeping this honest

Two logs make this runbook better over time, and both are cheap:

- **Config-guide backlog** — every config ticket you execute, one line. This is
  the input for writing guides, which is what moves those tickets off the queue
  permanently.
- **Redirect outcomes** — when a redirect bounces back because the DSO could not
  do it, note the school. That is how the per-school capability picture gets
  built, and it is the missing input for the roster branch.
