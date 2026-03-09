# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose

Dagster asset and resource for **LDAP/Active Directory** — used to sync staff
directory data (user accounts, group memberships, role assignments) from the
school network's AD instance.

## Factory: `build_ldap_asset()`

Produces a non-partitioned GCS Avro asset. Runs an LDAP search with configurable
`search_base`, `search_filter`, and `attributes` list.

Post-processes results: multi-value attributes (e.g., `member`, `memberOf`,
`proxyAddresses`) are kept as lists; datetime attributes (Windows LDAP timestamp
format) are converted to ISO strings.

## Resource: `LdapResource`

NTLM-authenticated LDAP3 connection over SSL. `search()` paginates via LDAP
paged results control and returns all entries as dicts.
