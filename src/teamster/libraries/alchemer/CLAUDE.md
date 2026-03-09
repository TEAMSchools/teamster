# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

**Alchemer** (formerly SurveyGizmo) survey platform integration.

**Note**: The asset factory (`build_alchemer_assets`) is disabled in `assets.py`
(commented out). Only the resource, schema, and sensor are active.

## Files

**`resources.py`** (`AlchemerResource`): Wraps the `alchemer` Python SDK.
Authenticates with `api_token` + `api_token_secret`. Exposes `_client` (an
`AlchemerSession`).

**`schema.py`**: Avro schemas for survey, survey question, campaign, and
response objects.

**`sensors.py`**: Sensor for detecting new/updated survey responses (active).

## Notes

When re-enabling the asset factory, it uses `DynamicPartitionsDefinition`
partitioned by `survey_id`.
