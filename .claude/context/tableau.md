# Tableau MCP gotchas

Injected on the first `mcp__tableau__*` call. Everything here is about the MCP
server's own tools. Editing or publishing a workbook is a different job with its
own gate: **invoke the `tableau-workbook-xml` skill before writing any
`tableauserverclient` code**, and do not attempt a publish from memory. That
skill carries the checkers, the repack script, the non-production review-copy
publish, and the two typed confirmations a production publish requires.

Marks: **Verified** = observed against this server. **Inferred** = reported
once, never probed.

- **`viewFilters` sets Tableau PARAMETERS, not just filter fields — this is the
  whole QA loop for a parameterised dashboard.** Pass the parameter's display
  name as the key and its value as the string, exactly as the parameter's
  allowable-values list spells it, alongside any real filters:

  ```text
  get-view-image(viewId=..., viewFilters={
      "Aimline Granularity Parameter": "Measure Standard",
      "Aimline Comparison Item Parameter": "Benchmark",
      "Granularity Options": "Reading Accuracy (ORF-Accu)"})
  ```

  Render at 1000x640 or larger to read BAN and bar labels.

- **Read the numbers off `get-view-image`, not `get-view-data`.** On a
  DASHBOARD, `get-view-data` returns only the first sheet (one BAN tile), so it
  cannot QA the rest. The image carries every tile and every bar.
- **A blank render usually means a stale filter member, not a broken call.** A
  filter on a calculated field whose domain changes with a parameter keeps its
  old selection; when the parameter moves, that member no longer exists and the
  view filters to nothing. Same cause when the dashboard looks dead after a
  parameter switch in the browser. The workbook fix is Edit Filter > General >
  "Use all"; to confirm from here, pass the new domain's value explicitly in
  `viewFilters` and see whether it renders.
- **A value that does not change proves nothing about whether a parameter
  applied.** Check a mark that MUST move under the parameter. A deliberately
  parameter-independent mark, such as a BAN, reads the same either way and
  falsely suggests parameters are unsupported.
- **The MCP is read-only.** Verified: every tool in this deployment is a `get-`,
  `list-`, `query-`, `search-` or `generate-pulse-*`. There is no publish, no
  workbook edit, no group mutation. Do not look for one. Workbook content can
  still be edited and republished from this Codespace with
  `tableauserverclient`; that is the skill's job, not the MCP's.
- **No tool returns calculated-field text.** Inferred. `get-workbook` and
  `list-workbooks` return workbook, view and datasource metadata, never the
  formula, and there is no Metadata API GraphQL passthrough. Row-level-security
  calculations cannot be audited from the MCP: checking which workbooks carry a
  branch, or searching for `USERNAME()` against a literal, happens outside it,
  by downloading the workbook through the skill.
- **Both metadata paths fail on an embedded extract.** Verified; do not re-test
  that case:

  | Tool                      | Result                                        |
  | ------------------------- | --------------------------------------------- |
  | `get-datasource-metadata` | HTTP 500                                      |
  | `query-datasource`        | `Unable to retrieve data source information.` |

  `get-datasource-metadata` reaches the Metadata API only for published
  datasources, and even then returns field names, types and roles, not formulas.
  `query-datasource`'s inline `calculation` parameter is not a way round it.

- **`get-workbook` gives the workbook-to-table mapping.** Inferred. Its
  `upstreamDatasources` array returns each datasource's name, luid and type, and
  it worked for embedded extracts. That maps a workbook to its dbt model in one
  call, and it also shows stale attached datasources. Use it before asking the
  user to read the Data pane.
- **The MCP cannot test a persona.** `scripts/tableau-mcp-launch.sh`
  authenticates with one fixed personal access token from 1Password, with no
  per-user credential, so `get-view-data` and `query-datasource` return that
  identity's rows for every user of the MCP. A render or query through it cannot
  distinguish an applied row-level-security gate from a broken one. The probe
  that can is in the skill's `references/build-workflow.md`.
- **`search-content` ranks, `list-*` enumerates.** Inferred. `search-content`
  returns one ranked page of top matches, not every match. When completeness
  matters, use `list-workbooks` with a filter.
- **`401002: Invalid authentication credentials` on a Tableau session.** Sign in
  fresh and retry. The MCP holds a session on its token for its process life, so
  avoid MCP calls during a scripted publish.
