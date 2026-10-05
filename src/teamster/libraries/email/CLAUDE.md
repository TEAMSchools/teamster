# CLAUDE.md — `teamster/libraries/email/`

SMTP email delivery for Dagster ops — used to send outbound emails to recipient
lists from BigQuery extract results.

## Files

**`resources.py`** (`EmailResource`): SMTP client with STARTTLS. Provides
`send_message()` for sending a single email with optional HTML alternative body.
It reconnects once on `SMTPServerDisconnected` and raises every other SMTP
error, so callers decide whether a failed send fails the run. Do not re-enable
`SMTP.set_debuglevel`: it writes the AUTH exchange, password included, to the
run logs. `chunk_size` controls BCC batch size for `send_email_op`.

**`ops.py`**:

- `send_email_op` splits recipients into BCC batches of `chunk_size` and sends
  every batch the same body.
- `send_personalized_email_op` groups rows by their `email` key and sends each
  person one email, rendering Jinja templates with that person's rows as
  `items`. The HTML template autoescapes. It sleeps between sends to honor
  `messages_per_minute`. It skips a failed recipient, raises `Failure` at the
  end if any send failed, and stops early after `max_consecutive_failures` in a
  row.
