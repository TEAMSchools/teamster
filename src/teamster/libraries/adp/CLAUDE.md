# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Two ADP product integrations:

- `workforce_now/` — ADP Workforce Now (HR/payroll system) via API and SFTP
- `workforce_manager/` — ADP Workforce Manager (time & attendance) via API

## `workforce_now/api/`

**`resources.py`** (`AdpWorkforceNowResource`): OAuth2 client using
`BackendApplicationClient` with mutual TLS (cert + key files). Calls ADP's REST
API for worker data.

**`ops.py`** (`adp_wfn_update_workers_op`): Op that updates ADP worker records —
work email and custom string fields — by POSTing to ADP's event API. Used in
provisioning pipelines triggered by LDAP/directory sync.

**`schema.py`** / **`utils.py`**: Avro schemas and utility helpers for ADP WFN
API responses.

**`workforce_now/sftp/schema.py`**: Avro schemas for ADP WFN SFTP file drops
(payroll reports).

## `workforce_manager/`

**`resources.py`** (`AdpWorkforceManagerResource`): REST client for ADP
Workforce Manager (time tracking, accruals).

**`assets.py`** (`build_adp_wfm_asset()`): Factory producing assets that fetch
report data from ADP WFM, parse CSV responses with pandas, and write Avro to
GCS. Supports daily + static multi-partitioning (by report type).

**`schema.py`**: Avro schemas for WFM report outputs.

## `payroll/`

**`schema.py`**: Avro schemas for ADP payroll SFTP extracts. No asset factory
(assets are built in the code location directly).
