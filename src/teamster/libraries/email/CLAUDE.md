# CLAUDE.md — `teamster/libraries/email/`

Outbound email for Dagster ops — sends to recipient lists from BigQuery extract
results.

## Files

**`resources.py`**:

- `GraphEmailResource` sends as one mailbox through Microsoft Graph `sendMail`
  with app-only (client credentials) auth. It caches the token and refreshes it
  5 minutes before expiry, retries 429 and 5xx with backoff, and raises
  `requests.HTTPError` on any other rejection. The Entra app needs Application
  `Mail.Send` scoped in Exchange to the sender mailbox. Use this for new email
  work: Exchange Online is retiring password (basic) SMTP sign-in.
- `EmailResource` is the older SMTP client (STARTTLS, password login). It logs
  and swallows send errors. Do not re-enable `SMTP.set_debuglevel`: it writes
  the AUTH exchange, password included, to the run logs.

**`ops.py`**:

- `send_personalized_email_op` (Graph) groups rows by their `email` key and
  sends each person one HTML email, rendering an autoescaped Jinja template with
  that person's rows as `items`. It sleeps between sends to honor
  `messages_per_minute`, since Exchange's 30-per-minute mailbox limit applies to
  Graph too. It skips a failed recipient, logs failures without the address,
  raises `Failure` at the end if any send failed, and stops early after
  `max_consecutive_failures` in a row.
- `send_email_op` (SMTP) splits recipients into BCC batches of `chunk_size` and
  sends every batch the same body.
