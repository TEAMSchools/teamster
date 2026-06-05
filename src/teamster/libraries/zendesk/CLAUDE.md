# CLAUDE.md — `teamster/libraries/zendesk/`

**Zendesk** customer support platform integration (REST API).

- **`resources.py`** (`ZendeskResource`): REST client with `get()`, `put()`, and
  `post()` methods.
- **`ops.py`** (`zendesk_user_sync_op`): Zendesk user sync.
- **`schema.py`**: Pydantic models (`Minutes`, `TicketMetric`).
