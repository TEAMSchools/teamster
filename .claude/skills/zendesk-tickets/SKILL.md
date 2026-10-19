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
- The skill is read-only. The client sends only GET requests, and the
  deliverable for any reply, note, or field change is a draft the user pastes
  into Zendesk so it posts under their own name. When the user asks to post,
  send, or write to Zendesk directly, show the draft and tell them the skill
  cannot post: pasting it is the only way. Keep every Zendesk request inside the
  script's functions, whatever the phrasing. A request written by hand with the
  token posts as the token's owner on the data team and counts toward that
  person's ticket statistics.
- Ask "public or internal?" in plain words every time for `draft_comment`, even
  when it seems obvious. `public` has no default. A macro decides its own
  visibility; the draft reports it.
- Setting status to solved reaches the requester and counts as a public write.
- Only the macro `Data - Close Out Older Ticket` and the `Assign to ...` family
  draft. The script refuses others.
- Thread text is PII: staff names, family names, student details. It stays in
  the terminal and the session scratchpad. An issue or PR that stems from a
  ticket says "Zendesk ticket 12345" and a redacted gist, never a quote. Redact
  student details to `Student A` before anything leaves the terminal, and post
  to Slack only in the data team channel.

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
5. Delete the test file for the ticket when it is done. It holds thread text.

## Queue

`queue()` lists unsolved tickets in Data and Teaching & Learning, oldest first.
`queue(groups=["Technology"])` names another group.

## Triage

Ask the runner's name once per session; it signs internal notes.

```python
from zendesk_tickets import draft_comment, draft_macro

draft_comment(
    <id>, "<text>", public=False, runner="<name>",
    status="pending", assignee="<first name>", category="<option name>",
)
draft_macro(<id>, "Data - Close Out Older Ticket", runner="<name>")
```

Before a `draft_comment` call, ask public or internal, every time; pass a real
`True` or `False`, nothing else. Run the draft call, show the printed draft
verbatim, tell the user it is theirs to paste into Zendesk, and stop. A
field-only change (status, assignee, category) is still a draft: the user makes
the change in Zendesk. Names resolve case-insensitively: a category by full name
(`Data::PowerSchool`) or unique last segment, an assignee by first name, full
name, or email among the ticket's group, a group by name. A `TicketError`
message is written for the user; show it verbatim.

## When to reach for the warehouse

Counts and trends across months go to `kipptaf_marts.fct_support_tickets`
through the BigQuery MCP, not to this script. The warehouse has no ticket
comments and lags the sync, so research on one ticket stays on the API.
