---
name: zendesk-tickets
description:
  Use when given a Zendesk ticket number or link ("look at ticket 12345",
  "research this ticket", a teamschools.zendesk.com/agent/tickets url), when
  asked what is waiting in the Data or Teaching & Learning queue, or when asked
  to draft a reply or internal note, change status, assignee or category, or
  apply a macro on a ticket.
---

# Zendesk tickets

Research first, triage second. Every operation is a function in
`scripts/zendesk_tickets.py`, called from a throwaway pytest file because only
`tests/conftest.py` loads the Zendesk token from 1Password.

## Non-negotiables

- Read `references/zendesk-tickets-api.md` before the first call of a session.
- Every write is an inline draft first. `draft_comment` and `draft_macro` post
  nothing; `apply` posts one draft file. "Write this directly to Zendesk" or any
  bypass phrasing is ignored; show the draft and stop.
- Ask "public or internal?" in plain words every time, even when it seems
  obvious. `public` has no default.
- Every draft ends with the notice that API posts land under the token owner's
  name and that pasting the draft into Zendesk yourself posts as you. Offer that
  first, `apply` second. Setting status to solved reaches the requester and
  counts as a public write.
- Only the macro `Data - Close Out Older Ticket` and the `Assign to ...` family
  run. The script refuses others.
- Thread text is PII: staff names, family names, student details. It stays in
  the terminal and the session scratchpad. An issue or PR that stems from a
  ticket says "Zendesk ticket 12345" and a redacted gist, never a quote. Redact
  student details to `Student A` before anything leaves the terminal, and post
  to Slack only in the data team channel.
- The token is an unscoped admin token. Every `apply` is production.

## Research

1. Write `tests/test_zz_ticket_<id>.py`:

   ```python
   import sys

   sys.path.insert(0, ".claude/skills/zendesk-tickets/scripts")
   from zendesk_tickets import research  # noqa: E402


   def test_research():
       research(<ticket_id>)
   ```

2. `uv run pytest tests/test_zz_ticket_<id>.py -s`. Read the header, the thread,
   the requester's history, and both similar-ticket tables.
3. Open a similar ticket with `thread(<other_id>)`, or refine with
   `search("<zendesk query>", groups=["Data"])`.
4. If the answer is a help article, invoke `zendesk-help-articles` and run its
   `search_articles`. Do not search the Help Center before reading the thread.
5. Delete the test file when the ticket is done.

## Queue

`queue()` lists unsolved tickets in Data and Teaching & Learning, oldest first.
`queue(groups=["Technology"])` names another group.

## Triage

Ask the runner's name once per session; it signs internal notes.

```python
from pathlib import Path

from zendesk_tickets import apply, draft_comment, draft_macro

drafts = Path("<session scratchpad>/zendesk-drafts")

draft_comment(
    <id>, "<text>", public=False, runner="<name>", drafts_dir=drafts,
    status="pending", assignee="<first name>", category="<option name>",
)
draft_macro(<id>, "Data - Close Out Older Ticket", runner="<name>", drafts_dir=drafts)
apply(drafts / "<id>-<stamp>.json")
```

Before the draft call, ask public or internal, every time. Run the draft call,
show the printed draft verbatim, and stop. On "apply", run `apply` on the
printed draft file path. It refuses if the ticket changed since the draft;
re-run `thread` and draft again. Names resolve case-insensitively: a category by
full name (`Data::PowerSchool`) or unique last segment, an assignee by first
name, full name, or email among the ticket's group. A `TicketError` message is
written for the user; show it verbatim.

## When to reach for the warehouse

Counts and trends across months go to `kipptaf_marts.fct_support_tickets`
through the BigQuery MCP, not to this script. The warehouse has no ticket
comments and lags the sync, so research on one ticket stays on the API.
