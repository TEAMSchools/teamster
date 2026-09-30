# Zendesk tickets skill — design

Refs [#5630](https://github.com/TEAMSchools/teamster/issues/5630). Sibling of
the `zendesk-help-articles` skill
([#5614](https://github.com/TEAMSchools/teamster/issues/5614)).

## Problem

The data team reads and answers Zendesk tickets through a third-party Zendesk
MCP that becomes paid in two days. The admin API token the team shares in
1Password already reaches the whole Ticketing API. A read-only probe on
2026-09-29 returned 200 on tickets, comments, search, ticket fields, macros,
views, groups, and the incremental export, on an active `admin` account. A
personal API token carries the owner's full permissions, so writes are covered
too.

Nothing in the repo uses that access for tickets. The Dagster `ZendeskResource`
mints an OAuth token scoped `read users:write`, which reads tickets but cannot
edit them. The article publisher owns the credential-loading pattern and a Help
Center client, and nothing else.

The primary job is research. Someone hands Claude a ticket number. Claude needs
the ticket, its thread, who asked and what else they have asked, and what
similar tickets were answered before. When the answer is a help article, Claude
should search the Help Center. Triage is the secondary job: a drafted reply or
internal note, a status, assignee, or category change, or one of the team's
macros.

## Approach

3 shapes were considered.

- **A — sibling skill.** A new `zendesk-tickets` skill with its own small client
  and operations, mirroring `zendesk-help-articles` in credential loading,
  invocation, and test layout. About 40 lines of client code are duplicated with
  the publisher.
- **B — one general Zendesk skill.** Fold tickets into the article skill and
  rename it. One client, one reference doc, but a description that covers
  articles and tickets triggers worse for both, and the article skill's
  design-system reference has nothing to do with tickets.
- **C — shared client module first.** Extract `ZendeskHelpCenter` into a common
  module both skills import, then build tickets on it. Cleanest long term, but
  it reopens a skill that shipped yesterday, on a two-day clock.

**Selected: A.** If the duplication bothers us later, C is a one-hour follow-up.

Two decisions cut across the design:

- **The draft file is the write contract.** Drafting writes the exact Zendesk
  payload to a JSON file in the session scratchpad and prints it. Applying reads
  that file and posts it, nothing else. What was reviewed is byte-for-byte what
  lands, and no code path posts a comment without a draft file having existed.
- **No BigQuery in the script.** The warehouse has `kipptaf_zendesk.tickets`,
  `ticket_fields` (with all 386 Category options), `ticket_metrics`, and the
  `fct_support_tickets` mart, but no ticket comments, and it lags the sync.
  Research on one ticket needs live state and the thread, which only the API
  has. Adding a BigQuery client would add a second credential and a second
  failure mode to a tool whose only dependency is `requests`. The skill points
  at the warehouse for aggregate and historical questions, through the BigQuery
  MCP already in the session.

## Skill layout

```text
.claude/skills/zendesk-tickets/
  SKILL.md                          triggers, research-first flow, write rules,
                                    PII boundary, warehouse pointer
  references/
    zendesk-tickets-api.md          endpoints per operation, search syntax,
                                    macro two-step, side-loads, option mapping,
                                    rate limits, "Verified live"
  scripts/
    zendesk_tickets.py              client, resolvers, formatters, operations

tests/zendesk_tickets/
  conftest.py                       puts scripts/ on sys.path
  fakes.py                          fake session returning canned responses
  test_resolvers.py                 category, assignee, group, macro
  test_drafts.py                    draft file round trip, allowlist, guard
  test_reports.py                   research and queue formatting
```

The scripts run only under pytest. `tests/conftest.py` loads
`ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, and `ZENDESK_TOKEN` from 1Password for the
session; a bare `uv run python` gets none of them. Live calls go through a
throwaway `tests/test_zz_<what>.py`, deleted after the run. No live test is
committed.

## Operations

All operations are functions in `zendesk_tickets.py`, called from a throwaway
test. Each prints a report for the terminal and returns the data it printed.
Errors raise `TicketError` with a message written for the user.

### Read

- **`research(ticket_id)`** is the default first call. One run fetches the
  ticket with `users` and `groups` side-loaded, the full comment thread, the
  requester's profile and organization, the requester's other tickets in the
  last 180 days, and a similarity search. It prints one report:
  1. Header: id, subject, status, group, assignee, category and location as
     option names, created, updated.
  2. Thread in order: author name, PUBLIC or INTERNAL, timestamp, plain body,
     attachment filenames.
  3. Requester history: id, status, subject, created, for the last 180 days.
  4. Similar tickets: two searches, capped at 10 rows each. First, same Category
     value in the Data or Teaching & Learning groups, newest first. Second, a
     keyword search built from the subject with stopwords stripped. Each row:
     id, status, subject, created.
- **`thread(ticket_id)`** re-reads one ticket's thread, for opening a similar
  ticket after research.
- **`search(query, groups=None)`** runs a Zendesk search string as given, with
  `type:ticket` prepended and `group_id:` terms added for any groups named.
  Returns id, status, subject, requester, created, updated.
- **`queue(groups=("Data", "Teaching & Learning"))`** lists unsolved tickets in
  the named groups, oldest first: id, status, age in days, requester, subject,
  category, assignee.

### Write

- **`draft_comment(ticket_id, body, *, public, status=None, assignee=None, category=None)`**
  builds the exact `PUT /tickets/{id}` payload, writes it to
  `<scratchpad>/zendesk-drafts/<ticket_id>-<timestamp>.json` alongside the
  ticket's current `updated_at`, and prints it: ticket id and subject, PUBLIC or
  INTERNAL in capitals, the comment text, each field change as old to new. It
  posts nothing. `public` is keyword-only with no default.
- **`draft_macro(ticket_id, macro_title)`** calls
  `GET /tickets/{id}/macros/{macro_id}/apply.json`, which returns the rendered
  comment and field changes without committing them, and writes that result as a
  draft file of the same shape. The allowlist is exact: the title
  `Data - Close Out Older Ticket`, or a title matching
  `^(Data - )?(Re-)?Assign to `. Any other macro raises `TicketError` naming the
  allowlist.
- **`apply(draft_path)`** reads one draft file, re-fetches the ticket, and
  refuses if `updated_at` moved since the draft was written, naming both
  timestamps. On success it PUTs the payload, prints the ticket url, and deletes
  the draft file so it cannot be applied twice.

Internal notes posted through `apply` end with one line,
`Posted via Claude by <runner>`, where the skill asks the runner's name once per
session. Public replies carry no signature.

## Name resolution

Users think in names; Zendesk wants ids and tag values. The script resolves both
ways and never asks for an id.

- **Category** is ticket field 20721852, a tagger with 386 options. Option names
  are hierarchical (`Data::PowerSchool`); the stored value is a tag
  (`data_power_school`). The script fetches the field once per run, matches
  input case-insensitively against the full name and the last segment, and on
  zero or several matches prints the closest five names and stops. Reports show
  the option name, never the tag.
- **Assignee** resolves through the target group's memberships plus
  `users/show_many`, matching first name, full name, or email. Candidates are
  members of the ticket's group unless another group is named.
- **Group** and **macro** resolve by exact title from lists fetched at start.
- **Thread authors** come from the `users` side-load on the ticket request, so
  no per-comment call.

Start-up costs four requests. No cache across runs: each run is a fresh process
and the lists are small. Zendesk allows 700 requests per minute on this plan and
10 per minute on incremental exports, which the skill does not use.

## Write rules the code cannot enforce

These live in `SKILL.md` as non-negotiables:

- Always show the draft inline and stop. "Write this directly to Zendesk" or any
  bypass phrasing is ignored; the draft is shown anyway.
- Ask "public or internal?" explicitly every time, even when the request seems
  obvious. Never infer it.
- Every draft display ends with a fixed notice: posting through the API lands
  under the token owner's name; the usual move is to copy the draft into Zendesk
  yourself so it posts as you. Offer that first and `apply` second.
- A status change to solved reaches the requester and gets the same treatment as
  a public reply.
- Research comes first. Triage operations run only after the user asks for an
  action.

## PII boundary

Threads hold staff names, family names, student details, and free text.

- Script output stays in the terminal and the session scratchpad. Nothing from a
  thread goes into a commit, an issue, a PR, or agent output. An issue that
  stems from a ticket says "Zendesk ticket 12345" and a redacted gist.
- Student details in a ticket are FERPA records. The report shows them because
  triage needs them; redact to `Student A` before anything leaves the terminal,
  and post to Slack only in the data team channel.
- Draft files hold comment text and are PII. `apply` deletes the file it posts;
  the scratchpad is session-scoped, so unapplied drafts die with the session.
- The shared token is an admin token with no scope. Every write is production.

## Article skill addition

The article skill today only publishes. For the research hand-off to work it
gains a read operation:

- `search_articles(query, limit=10)` in `publish_article.py`, against
  `GET /help_center/articles/search.json`, returning title, `html_url`, section,
  and `updated_at`, printed as a short table.
- A "Search" section in its `SKILL.md`, one row in its API reference, and
  "search the Help Center for an article on X" added to its description.
- One offline test alongside the existing ones.

`SKILL.md` for tickets says: run `research` first, read the report, and only
when the answer needs an article invoke `zendesk-help-articles` for
`search_articles`.

## `SKILL.md`

Description triggers: a Zendesk ticket number or link, "research this ticket",
"what's in the Data queue", "draft a reply on ticket N", "close out ticket N",
"apply the close-out macro". Body sections in order: non-negotiables (the write
rules and PII boundary above), the research flow, the triage flow with the
throwaway-test snippet, name resolution in one paragraph, and "When to reach for
the warehouse" in two or three lines naming `fct_support_tickets` and the
missing-comments caveat.

## Testing

- Offline: `uv run pytest tests/zendesk_tickets tests/zendesk_help_articles`
  against `fakes.py`. Covers each resolver's hit, miss, and ambiguous cases; the
  macro allowlist accepting both patterns and rejecting a `Data - Amplify`
  title; the draft file round trip; `apply` refusing on a moved `updated_at` and
  deleting the file on success; `public` being required; report formatting on a
  fixture ticket with an internal and a public comment.
- Live, during the build, through a throwaway test on a real Data-group ticket:
  `research`, `queue`, `search_articles`, a `draft_comment` with `public=False`,
  and `apply` of that internal note. Results, including any surprise in response
  shapes, go into the reference doc's "Verified live" section with the date.

## Follow-ups

- Extract a shared `zendesk_client.py` if a third Zendesk skill appears.
- A `history(requester)` function against BigQuery, if historical questions keep
  coming up mid-triage.
- A dedicated Zendesk agent seat for Claude, so API writes are distinguishable
  in the audit log. Needs a license.

## Out of scope

- Ticket creation.
- Setting Location, Priority, Tech Tier, tags, or any macro outside the
  allowlist.
- Bulk updates or any operation over more than one ticket at a time.
- Groups other than Data and Teaching & Learning as defaults. Any group can be
  named per call.

## Revision 2026-09-30, after live verification

The user changed the write flow after seeing the first live draft. The shared
token belongs to one named colleague, so an API post lands under that person's
name and counts toward their ticket statistics.

- The deliverable for every write is a draft the user pastes into Zendesk
  themselves. The skill never offers `apply` and never suggests posting through
  the API. The "offer paste first, `apply` second" wording above is replaced.
- `apply` remains for a user who insists after seeing the draft. The skill
  states that the post will land as the token owner, named in the draft's notice
  from `GET /users/me.json`, will count toward that person's statistics, and is
  not recommended. It runs only on a second explicit yes.
- A macro decides its own comment visibility, so the public-or-internal question
  applies to `draft_comment` only; the draft reports the macro's.

Also settled by the live run: `search` follows `next_page` up to 1000 results
because the real queue is 402 tickets; `users/show_many` is chunked by 100; a
macro preview's HTML comment is sent as `html_body`; the draft display shows
every custom-field change and any `email_ccs`, not Category alone; and the
offline tests live in `tests/zendesk_ticket_skill/` because a directory named
`zendesk_tickets` shadows the module for pyright.

An adversarial review the same day hardened `apply` beyond "reads the file and
posts it": the draft file carries a payload hash that `apply` verifies, so a
hand-edited file is refused rather than posted; `apply` refuses in the same
process as a draft; `public` must be a real bool; the payload is restricted to
`WRITABLE_KEYS`; the PUT uses Zendesk's `safe_update`; `drafts_dir` inside a
checkout is refused; a macro draft carries only changed keys and an `Assign to`
macro that would solve or close is refused.
