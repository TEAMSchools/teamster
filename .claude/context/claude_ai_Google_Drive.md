# Google Drive MCP gotchas

`read_file_content` on a multi-tab Google Sheet returns every tab concatenated
into one text blob with **no tab names and no cell addresses**. You can quote a
value but you cannot say where it came from.

Consequence: a tab named `DO NOT USE THESE` is indistinguishable from an
authoritative one. This already produced a false "the goals sheet contradicts
itself" report — the conflicting numbers were on a deprecated tab that the flat
output gave no way to identify.

Rules that follow:

- **Never escalate unattributable content to a finding.** Say "this text exists
  somewhere in the file", not "these two tables disagree". A discrepancy claim
  requires knowing which tab each side is on.
- **Blank-line breaks in the output are a weak hint, not tab boundaries.** One
  tab holding two tables separated by empty rows renders as a single block, so
  block count does not equal tab count.
- **Ask the user which tab, or ask them to paste it.** A paste carries
  provenance for free because they choose the tab. This is the same
  Excel-to-Notepad flow the CARAT scale-score work uses.

`mcp__claude_ai_Google_Drive__*` runs as the **user's** identity. ADC
(`codespaces@teamster-332318.iam.gserviceaccount.com`) is a different principal
and is often not shared on KIPP Forward planning docs — a Sheets API call for
those returns 403 while the Drive MCP read succeeds. The Sheets API is the only
way to get tab names and cell addresses, so when a doc will not be shared with
the service account, tab-level precision is simply unavailable; plan around it
rather than retrying.

Distinct identity again for dbt: a BigQuery Sheets **external table** reads
under the BigLake connection, not under either of the above. A sheet readable
via the Drive MCP is not necessarily readable by a dbt source.

`get_file_metadata` is worth calling before quoting anything from a shared doc —
it returns `title`, `owner`, and `modifiedTime`, which are the provenance facts
the content itself does not carry.

- **Drive MCP `read_file_content` returns only the first sheet tab** — to read a
  specific tab of a multi-tab Google Sheet, use the Sheets API via
  `uv run --with google-api-python-client` with `range="'Tab Name'!A1:Z"` (ADC
  has the scope), not the Drive MCP read.
