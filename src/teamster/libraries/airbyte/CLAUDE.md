# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Airbyte Cloud integration helper. Provides a schedule factory that triggers
Airbyte syncs on a cron schedule outside of Airbyte's built-in scheduler.

## File

**`schedules.py`** (`build_airbyte_start_sync_schedule()`): Creates a Dagster
schedule backed by a placeholder job. When the schedule fires, it calls
`airbyte.get_client().start_sync_job(connection_id)` directly via the Airbyte
Cloud workspace resource. Always returns `SkipReason` (no Dagster runs are
created; the sync is triggered as a side effect).

This pattern is used when Airbyte asset materialization is tracked externally
(via `dagster-airbyte` asset specs) but the sync trigger needs to be managed by
Dagster's scheduler.
