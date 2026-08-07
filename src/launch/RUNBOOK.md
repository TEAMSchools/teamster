# Launch page catalog — runbook

The task sequence for getting `links.yml` from a scraped starting point to a
catalog we would put in front of staff.

[README.md](README.md) is the reference: what the directory is, what each field
means, and what "verified" requires. This file is the order to do things in and
who owns what.

## The goal

**All 46 entries in `links.yml` carry `status: verified`.**

That is the whole deliverable. Everything else here is in service of it or
explicitly someone else's job.

---

## Step 0 — Access, on day one

Nothing else can start until these work. Check all of them the first morning and
escalate immediately if any is missing; waiting until Wednesday to discover a
Tableau access gap loses the week.

- [ ] **Tableau** — `tableau.kipp.org`. Needed for 35 of the 46 entries. This is
      the one that blocks everything.
- [ ] **Google Drive** — the GPA Rosters, the Student Contact Info Feeds, and
      the Sheets behind the AppSheet apps.
- [ ] **AppSheet** — the three apps.
- [ ] **A way to edit this repository.** See _Working agreement_ below.

## Step 1 — Verify the catalog entries

The week's work. For each entry, apply the five checks in
[README.md](README.md#the-work) and change `status: needs-review` to
`status: verified`.

Suggested order:

1. **The tools you already know**, to confirm the pattern before scaling up.
1. **The rest alphabetically.** Most are quick — open it, confirm the name,
   tighten the description, decide the audiences.
1. **Anything Google-hosted gets the sharing check** described in README.md.
   Non-optional, and it is the one check with a real consequence if skipped.

Roughly 46 entries at ten to fifteen minutes each is about a day and a half of
focused time. The rest of the week is the judgment calls and what you turn up
along the way.

### Bring these to Anthony rather than guessing

Five entries need a decision, not a lookup. They are marked `TODO(verify)` in
the file. Batch them into one conversation rather than blocking on each:

- **`Home Instruction Tracker`** — resolves to two different URLs depending on
  which page of the old site you came from, and one of the two descriptions
  plainly belongs to a different tool.
- **`Literacy Tool (ELIT)` and `Early Literacy Tool (ELIT)`** — different
  dashboards, nearly identical names. Both live. Probably need renaming.
- **`Testing Accommodations`** — two contradictory descriptions on the old site:
  assessment _results_ versus accommodation _requests_. Not the same thing.
- **`Stipend and Bonus Dashboard`** — described as a live dashboard, but the URL
  points at a help article.
- **The four entries with empty `audiences`** — `Early Literacy Tool`,
  `Leader PM App`, `Seat Tracker`, `Stipend App`. Nothing on the old site says
  who they are for.

### One open question worth raising

Clever, DeansList, Grow, and PowerSchool are named on the old Support page, but
all four link to the same Okta dashboard URL rather than to the apps themselves.
Should they be catalog entries at all, and if so, pointing at what?

## Step 2 — Flag what you find

You will be the first person to look at all 46 at once, which makes you the most
likely person to notice:

- A tool that appears twice under different names
- A tool that nobody has opened in years
- A tool missing from the list entirely
- A description that would confuse someone who did not already know the tool

Open an issue or leave a note. This is part of the job, not a distraction from
it — the duplicates and contradictions already found came from exactly this kind
of looking.

---

## Working agreement

**Editing.** Unless you already work in git day to day, use the GitHub web
editor: open `links.yml` on the branch, edit, and commit to a branch with a
short message. No local setup, no terminal. Someone will review and merge.

**Commit as you go**, not all at the end. A commit per batch of entries is easy
to review; one commit with 46 changed entries is not.

**Ask early.** Every judgment call in this file is one somebody else can answer
in two minutes. Guessing costs more than asking.

**Do not worry about** the rendering pipeline, Zendesk configuration or article
IDs, the `views.yml` intro copy, or the Our Team / support / blog content. All
handled elsewhere.

---

## Not intern work — owned by Anthony

### Triage the Google Sheets exposures

`src/dbt/kipptaf/models/exposures/google-sheets.yml` documents **63 Google
Sheets** the pipeline writes to, each with a URL and its upstream model. Only 7
are in `links.yml`.

**The question for each: is this canonical for staff access right now?** Three
answers, all common — yes and it belongs in the catalog; no, it is machine
plumbing; or no, it is dead and worth flagging.

This is deliberately not delegated. It needs someone who knows the history of
each sheet, and that context is slower to transfer than to apply.

**It also cannot be shortcut by sorting.** A first pass grouped the 63 by how
their names looked — integration feeds, personal one-offs, stale-by-title,
un-renamed model names, plausible candidates. That grouping was wrong:
staff-facing tools sit in every one of those buckets, including the ones that
looked most obviously like plumbing. There is no keyword rule and no scrape that
gets this right.

Two further reasons not to scrape the file:

- It is **not complete**. The four Student Contact Info Feeds — used from
  operations associates up to assistant superintendents — are not in it, or
  anywhere else in this repository.
- An exposure records _"this model feeds this artifact"_, a lineage fact. The
  catalog records _"a staff member might need to find this"_, an audience fact.
  The second is not derivable from the first.

**Sequencing note.** Triage output adds new entries to `links.yml`. If that
happens while the intern is working through the existing 46, both are editing
one file all week. Cleanest is for triage to produce a list that gets appended
and verified after the intern's pass, rather than direct concurrent edits.

### Findings to handle separately

Independent of triage, and independent of the catalog:

- **Nine exposures have no human label**, carrying the raw model name
  (`gsheets_student_contact_info`, `rpt_gsheets__athletic_eligibility`, and
  similar). Small dbt hygiene fix.
- **At least six are stale by their own titles** — named for school years or
  projects that have passed. If they still materialize nightly, that is compute
  spent on outputs nobody reads.
- **The four Student Contact Info Feeds are not tracked in this repository at
  all.** Worth establishing how they are maintained, since that determines
  whether an upstream schema change would break them silently.
