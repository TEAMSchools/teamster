# Launch page catalog — intern runbook

> **Work in progress.** Steps are being added as they are identified. This file
> is the task sequence; [README.md](README.md) is the orientation for the
> directory and the definition of what "reviewing an entry" means.

## Step: triage the Google Sheets exposures

**Not started. Needs someone who knows the tools — this cannot be done from the
names alone.**

`src/dbt/kipptaf/models/exposures/google-sheets.yml` documents **63 Google
Sheets** the data pipeline writes to, each with a URL and its upstream model.
Only 7 Sheets are currently in `links.yml`.

**The question for each of the 63: is this canonical for staff access right
now?**

Three answers are possible, and all three are common:

1. **Yes** — staff use it, it belongs in `links.yml` and in the Claude discovery
   skill.
1. **No, it is machine plumbing** — a vendor import, a system feed, an upload
   template. Nobody navigates to it.
1. **No, it is dead** — a one-off from a past year, a personal scratch copy, or
   superseded by something else. Worth flagging separately; several are still
   materializing nightly.

### Why this cannot be shortcut

An earlier attempt to sort these by name produced tidy-looking buckets —
integration feeds, personal one-offs, stale-by-title, un-renamed model names,
and plausible candidates. **That grouping was wrong.** Staff-facing tools turned
out to sit in every one of those buckets, including the ones that looked most
obviously like plumbing.

So there is no filter, no keyword rule, and no scrape that gets this right. It
is 63 individual decisions. Budget accordingly.

Two more reasons not to scrape:

- The exposures file is **not complete**. The four Student Contact Info Feeds —
  used by everyone from operations associates to assistant superintendents — do
  not appear in it, or anywhere else in this repository.
- An exposure records _"this model feeds this artifact"_, which is a lineage
  fact. The catalog records _"a staff member might need to find this"_, which is
  an audience fact. The second cannot be derived from the first.

### Output

For each of the 63, one of:

- A new `links.yml` entry (canonical for staff — follow README.md conventions,
  including the Drive sharing check)
- No entry, marked as plumbing
- No entry, flagged as dead or stale for follow-up

### Findings to raise separately as you go

These came out of a first pass and are worth fixing regardless of the triage
outcome:

- **Nine exposures have no human label** and carry the raw model name
  (`gsheets_student_contact_info`, `rpt_gsheets__athletic_eligibility`, and
  similar). Small dbt hygiene fix.
- **At least six are stale by their own titles** — named for school years or
  projects that have passed. If they still materialize nightly, that is compute
  spent on outputs nobody reads.
- **The four Student Contact Info Feeds are not tracked in the repository at
  all.** Worth establishing how they are actually maintained, since that
  determines whether an upstream schema change would silently break them.

## Steps still to be added

This runbook is incomplete. Further steps to be defined.
