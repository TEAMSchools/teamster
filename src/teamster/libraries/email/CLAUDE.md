# CLAUDE.md — `teamster/libraries/email/`

Outbound email for Dagster ops — sends to recipient lists from BigQuery extract
results.

## Files

**`resources.py`**:

- `MailSenderResource` is the base for senders with one
  `send_mail(to_email, subject, html_body)` call. Its `_request` retries 429,
  5xx, connection errors, and timeouts, and builds error messages without the
  request URL. `send_personalized_email_op` accepts any subclass.
- `ZapierWebhookEmailResource` posts `email`, `subject`, and `html` to a Zapier
  Catch Hook; the Zap's email step sends it. The webhook URL is a secret, so its
  errors are rebuilt outside the `except` block to keep the original exception
  (whose message can contain the URL) out of the logs. Success only means Zapier
  accepted the request; delivery errors show in the Zap's task history.
- `GraphEmailResource` sends as one mailbox through Microsoft Graph `sendMail`
  with app-only auth. It needs an Entra app with Application `Mail.Send` scoped
  in Exchange to the sender mailbox.
- `EmailResource` is the older SMTP client (STARTTLS, password login). It logs
  and swallows send errors. Exchange Online is retiring password SMTP sign-in,
  and it fails outright for a mailbox with 2FA. Do not re-enable
  `SMTP.set_debuglevel`: it writes the AUTH exchange, password included, to the
  run logs.

**`ops.py`**:

- `send_personalized_email_op` groups rows by their `email` key and sends each
  person one HTML email, rendering an autoescaped Jinja template with that
  person's rows as `items`. Guards against looking like bulk mail: a
  `messages_per_minute` pace (default 8, well under Exchange's 30), a
  `max_recipients` cap checked before anything sends, `dry_run`, and an
  `only_send_to` allowlist for test runs. It skips a failed recipient, logs
  failures without the address, raises `Failure` at the end if any send failed,
  and stops early after `max_consecutive_failures` in a row.
- `send_email_op` (SMTP) splits recipients into BCC batches of `chunk_size` and
  sends every batch the same body.
