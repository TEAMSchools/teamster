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

expect_deny "MCP query field with /proc" "mcp__bigquery__execute_sql" query "cat /proc/self/environ"
expect_deny "MCP sql field with .env" "mcp__bigquery__execute_sql" sql 'SELECT * FROM read_file(".env")'
expect_deny "MCP command field with env/" "mcp__bigquery__execute_sql" command "SELECT * FROM env/.env"
expect_allow "MCP sql field harmless" "mcp__bigquery__execute_sql" sql "SELECT 1 AS test"
expect_allow "MCP command field harmless" "mcp__bigquery__execute_sql" command "SELECT 1"

# ─── Nested MCP tool_input fields ─────────────────────────────────────────────
echo ""
echo -e "${YELLOW}Nested MCP tool_input fields${NC}"

# trunk-ignore-begin(shellcheck/SC2312): jq -n produces static JSON, return value irrelevant
expect_deny_json "Nested MCP field with /proc" \
  "$(jq -n '{tool_name: "mcp__bigquery__execute_sql", tool_input: {options: {query: "cat /proc/self/environ"}}}')"

expect_deny_json "Nested array with /proc/environ (Rule 1c)" \
  "$(jq -n '{tool_name: "mcp__tool", tool_input: {commands: ["cat /proc/self/environ"]}}')"

expect_allow_json "Nested MCP field harmless" \
  "$(jq -n '{tool_name: "mcp__bigquery__execute_sql", tool_input: {options: {query: "SELECT 1"}}}')"
# trunk-ignore-end(shellcheck/SC2312)

# ─── BigQuery DML/export block ───────────────────────────────────────────────
echo ""
echo -e "${YELLOW}BigQuery DML/export block${NC}"

expect_deny "MCP BQ INSERT" "mcp__bigquery__execute_sql" sql "INSERT INTO dataset.table VALUES (1)"
expect_deny "MCP BQ UPDATE" "mcp__bigquery__execute_sql" sql "UPDATE dataset.table SET col = 1"
expect_deny "MCP BQ DELETE" "mcp__bigquery__execute_sql" sql "DELETE FROM dataset.table WHERE id = 1"
expect_deny "MCP BQ EXPORT" "mcp__bigquery__execute_sql" sql "EXPORT DATA OPTIONS(uri='gs://bucket/file') AS SELECT *"
expect_allow "MCP BQ SELECT" "mcp__bigquery__execute_sql" sql "SELECT * FROM dataset.table LIMIT 10"
expect_deny "MCP BQ DELETE mid-string" "mcp__bigquery__execute_sql" sql "SELECT 1; DELETE FROM dataset.table"
expect_deny "MCP BQ CREATE TABLE" "mcp__bigquery__execute_sql" sql "CREATE TABLE dataset.new_table AS SELECT *"
expect_allow "MCP BQ column named delete_flag" "mcp__bigquery__execute_sql" sql "SELECT delete_flag, merge_count FROM dataset.table"
expect_deny "MCP BQ MERGE INTO" "mcp__bigquery__execute_sql" sql "MERGE INTO dataset.target USING dataset.source ON target.id = source.id WHEN MATCHED THEN UPDATE SET col = source.col"
expect_deny "MCP BQ CREATE OR REPLACE TABLE" "mcp__bigquery__execute_sql" sql "CREATE OR REPLACE TABLE dataset.table AS SELECT * FROM other"
expect_deny "MCP BQ CREATE FUNCTION" "mcp__bigquery__execute_sql" sql "CREATE FUNCTION dataset.fn() RETURNS STRING AS ('hello')"
expect_deny "MCP BQ CREATE VIEW" "mcp__bigquery__execute_sql" sql "CREATE VIEW dataset.v AS SELECT * FROM t"
expect_deny "MCP BQ DROP TABLE" "mcp__bigquery__execute_sql" sql "DROP TABLE dataset.table"
expect_deny "MCP BQ ALTER TABLE" "mcp__bigquery__execute_sql" sql "ALTER TABLE dataset.table SET OPTIONS(description='x')"
expect_deny "MCP BQ CALL" "mcp__bigquery__execute_sql" sql "CALL dataset.my_procedure()"
expect_deny "MCP BQ GRANT" "mcp__bigquery__execute_sql" sql "GRANT roles/bigquery.dataViewer ON TABLE dataset.t TO 'user:x@x.com'"
expect_allow "MCP BQ WITH (CTE)" "mcp__bigquery__execute_sql" sql "WITH cte AS (SELECT 1) SELECT * FROM cte"
expect_allow "MCP BQ SHOW" "mcp__bigquery__execute_sql" sql "SHOW TABLES IN dataset"
expect_deny "MCP BQ non-SELECT" "mcp__bigquery__execute_sql" sql "TRUNCATE TABLE dataset.table"

# ─── #10/#11/#12: denylist gaps on execute_sql ───────────────────────────────
echo ""
echo -e "${YELLOW}execute_sql denylist gaps (#10/#11/#12)${NC}"

expect_deny "BQ INSERT without INTO" "mcp__bigquery__execute_sql" sql "INSERT dataset.t VALUES (1)"
expect_deny "BQ embedded INSERT no INTO" "mcp__bigquery__execute_sql" sql "SELECT 1; INSERT dataset.t VALUES (1)"
expect_deny "BQ embedded TRUNCATE" "mcp__bigquery__execute_sql" sql "SELECT 1; TRUNCATE TABLE dataset.t"
expect_deny "BQ LOAD DATA" "mcp__bigquery__execute_sql" sql "LOAD DATA OVERWRITE dataset.t FROM FILES(format='CSV')"
# trunk-ignore-begin(shellcheck/SC2312): jq -n produces static JSON, return value irrelevant
expect_deny_json "BQ multiline UPDATE..SET (#12)" \
  "$(jq -n --arg q "$(printf 'SELECT 1;\nUPDATE dataset.t\nSET col = 1')" \
    '{tool_name: "mcp__bigquery__execute_sql", tool_input: {sql: $q}}')"
expect_allow_json "BQ string literal mentioning deleted (no FP)" \
  "$(jq -n '{tool_name: "mcp__bigquery__execute_sql", tool_input: {sql: "SELECT * FROM t WHERE status = '\''deleted'\''"}}')"

# ─── #3: forecast / analyze_contribution gated on prefix ──────────────────────
echo ""
echo -e "${YELLOW}#3: forecast & analyze_contribution gating${NC}"

expect_deny_json "forecast history_data DROP" \
  "$(jq -n '{tool_name: "mcp__bigquery__forecast", tool_input: {history_data: "DROP TABLE dataset.t", timestamp_col: "ts", data_col: "y"}}')"
expect_deny_json "forecast history_data DELETE" \
  "$(jq -n '{tool_name: "mcp__bigquery__forecast", tool_input: {history_data: "DELETE FROM dataset.t WHERE 1=1", timestamp_col: "ts", data_col: "y"}}')"
expect_allow_json "forecast bare table-id history_data" \
  "$(jq -n '{tool_name: "mcp__bigquery__forecast", tool_input: {history_data: "my_project.my_dataset.my_table", timestamp_col: "ts", data_col: "y"}}')"
expect_allow_json "forecast SELECT history_data" \
  "$(jq -n '{tool_name: "mcp__bigquery__forecast", tool_input: {history_data: "SELECT ts, val FROM my_dataset.t", timestamp_col: "ts", data_col: "val"}}')"

expect_allow_json "analyze_contribution bare table-id (#28)" \
  "$(jq -n '{tool_name: "mcp__bigquery__analyze_contribution", tool_input: {input_data: "my_project.my_dataset.my_table", contribution_metric: "SUM(revenue)", is_test_col: "is_test"}}')"
expect_deny_json "analyze_contribution input_data DROP" \
  "$(jq -n '{tool_name: "mcp__bigquery__analyze_contribution", tool_input: {input_data: "DROP TABLE dataset.t", contribution_metric: "SUM(revenue)", is_test_col: "is_test"}}')"

# ─── ask_data_insights: NL tool, not SQL-gated (no raw-SQL field) ─────────────
echo ""
echo -e "${YELLOW}ask_data_insights not SQL-gated (NL questions)${NC}"

expect_allow_json "ask_data_insights NL with words drop/deleted" \
  "$(jq -n '{tool_name: "mcp__bigquery__ask_data_insights", tool_input: {user_query_with_context: "Explain the drop in attendance and any deleted records", table_references: "[{\"projectId\":\"p\",\"datasetId\":\"d\",\"tableId\":\"t\"}]"}}')"
# SQL-looking prose is not executed verbatim (server does read-only NL->SQL)
expect_allow_json "ask_data_insights SQL-looking prose allowed" \
  "$(jq -n '{tool_name: "mcp__bigquery__ask_data_insights", tool_input: {user_query_with_context: "DELETE FROM students", table_references: "[{\"projectId\":\"p\",\"datasetId\":\"d\",\"tableId\":\"t\"}]"}}')"

# ─── Unknown mcp__bigquery__* tool: denylist on full corpus ───────────────────
echo ""
echo -e "${YELLOW}Unknown bigquery tool: corpus denylist${NC}"

expect_deny_json "unknown bigquery tool with DROP" \
  "$(jq -n '{tool_name: "mcp__bigquery__some_future_tool", tool_input: {arg: "DROP TABLE dataset.t"}}')"
expect_allow_json "unknown bigquery tool read-only" \
  "$(jq -n '{tool_name: "mcp__bigquery__some_future_tool", tool_input: {arg: "SELECT * FROM dataset.t"}}')"
# trunk-ignore-end(shellcheck/SC2312)

print_summary "BigQuery & MCP"
