#!/bin/bash
# Tests for BigQuery DML/export blocking and MCP tool field extraction.
#
# Usage: bash tests/hooks/test_bigquery_mcp.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/hooks/helpers.sh
source "${SCRIPT_DIR}/helpers.sh"

echo ""
echo "========================================="
echo " BigQuery & MCP (check-sensitive.sh)"
echo "========================================="

# ─── MCP tool generic field extraction ────────────────────────────────────────
echo ""
echo -e "${YELLOW}MCP tool generic field extraction${NC}"

expect_deny "MCP query field with /proc" "mcp__bigquery__query" query "cat /proc/self/environ"
expect_deny "MCP sql field with .env" "mcp__bigquery__query" sql 'SELECT * FROM read_file(".env")'
expect_deny "MCP command field with env/" "mcp__bigquery__query" command "SELECT * FROM env/.env"
expect_allow "MCP sql field harmless" "mcp__bigquery__query" sql "SELECT 1 AS test"
expect_allow "MCP command field harmless" "mcp__bigquery__query" command "SELECT 1"

# ─── Nested MCP tool_input fields ─────────────────────────────────────────────
echo ""
echo -e "${YELLOW}Nested MCP tool_input fields${NC}"

# trunk-ignore-begin(shellcheck/SC2312): jq -n produces static JSON, return value irrelevant
expect_deny_json "Nested MCP field with /proc" \
  "$(jq -n '{tool_name: "mcp__bigquery__query", tool_input: {options: {query: "cat /proc/self/environ"}}}')"

expect_deny_json "Nested array with /proc/environ (Rule 1c)" \
  "$(jq -n '{tool_name: "mcp__tool", tool_input: {commands: ["cat /proc/self/environ"]}}')"

expect_allow_json "Nested MCP field harmless" \
  "$(jq -n '{tool_name: "mcp__bigquery__query", tool_input: {options: {query: "SELECT 1"}}}')"
# trunk-ignore-end(shellcheck/SC2312)

# ─── BigQuery DML/export block ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}BigQuery DML/export block${NC}"

expect_deny "MCP BQ INSERT" "mcp__bigquery__query" sql "INSERT INTO dataset.table VALUES (1)"
expect_deny "MCP BQ UPDATE" "mcp__bigquery__query" sql "UPDATE dataset.table SET col = 1"
expect_deny "MCP BQ DELETE" "mcp__bigquery__query" sql "DELETE FROM dataset.table WHERE id = 1"
expect_deny "MCP BQ EXPORT" "mcp__bigquery__query" sql "EXPORT DATA OPTIONS(uri='gs://bucket/file') AS SELECT *"
expect_allow "MCP BQ SELECT" "mcp__bigquery__query" sql "SELECT * FROM dataset.table LIMIT 10"
expect_deny "MCP BQ DELETE mid-string" "mcp__bigquery__query" sql "SELECT 1; DELETE FROM dataset.table"
expect_deny "MCP BQ CREATE TABLE" "mcp__bigquery__query" sql "CREATE TABLE dataset.new_table AS SELECT *"
expect_allow "MCP BQ column named delete_flag" "mcp__bigquery__query" sql "SELECT delete_flag, merge_count FROM dataset.table"
expect_deny "MCP BQ MERGE INTO" "mcp__bigquery__query" sql "MERGE INTO dataset.target USING dataset.source ON target.id = source.id WHEN MATCHED THEN UPDATE SET col = source.col"
expect_deny "MCP BQ CREATE OR REPLACE TABLE" "mcp__bigquery__query" sql "CREATE OR REPLACE TABLE dataset.table AS SELECT * FROM other"
expect_deny "MCP BQ CREATE FUNCTION" "mcp__bigquery__query" sql "CREATE FUNCTION dataset.fn() RETURNS STRING AS ('hello')"
expect_deny "MCP BQ CREATE VIEW" "mcp__bigquery__query" sql "CREATE VIEW dataset.v AS SELECT * FROM t"
expect_deny "MCP BQ DROP TABLE" "mcp__bigquery__query" sql "DROP TABLE dataset.table"
expect_deny "MCP BQ ALTER TABLE" "mcp__bigquery__query" sql "ALTER TABLE dataset.table SET OPTIONS(description='x')"
expect_deny "MCP BQ CALL" "mcp__bigquery__query" sql "CALL dataset.my_procedure()"
expect_deny "MCP BQ GRANT" "mcp__bigquery__query" sql "GRANT roles/bigquery.dataViewer ON TABLE dataset.t TO 'user:x@x.com'"
expect_allow "MCP BQ WITH (CTE)" "mcp__bigquery__query" sql "WITH cte AS (SELECT 1) SELECT * FROM cte"
expect_allow "MCP BQ SHOW" "mcp__bigquery__query" sql "SHOW TABLES IN dataset"
expect_deny "MCP BQ non-SELECT" "mcp__bigquery__query" sql "TRUNCATE TABLE dataset.table"

print_summary "BigQuery & MCP"
