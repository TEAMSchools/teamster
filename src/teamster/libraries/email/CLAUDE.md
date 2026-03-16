# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

SMTP email delivery for Dagster ops — used to send batched outbound emails
(e.g., recipient lists from BigQuery extract results).

## Files

**`resources.py`** (`EmailResource`): SMTP client with STARTTLS. Provides
`send_message()` for sending a single email with optional HTML alternative body.
`chunk_size` controls BCC batch size to avoid SMTP limits.

**`ops.py`** (`send_email_op`): Dagster op that splits recipients into batches
of `chunk_size` and calls `email.send_message()` for each batch. Accepts a
`Config` class with `subject`, `text_body`, and optional `template_path` (HTML
template). Upstream ops pass `recipients` as a list of dicts with an `email`
key.
