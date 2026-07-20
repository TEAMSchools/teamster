# Cube API

How to query the Cube semantic layer — for external API developers, dashboard /
BI builders, and Claude MCP users. All three share one field surface: the
[Cube data catalog](../reference/cube-data-catalog.md) lists every view and the
fields it exposes.

## Start here

- **External / API developer** — read [Authentication](#authentication) then
  [Query format](#query-format); use the [REST example](#rest-api).
- **Dashboard / BI builder** — connect via the SQL API
  ([SQL example](#sql-api)); pick fields from the
  [catalog](../reference/cube-data-catalog.md). Access is filtered to your
  identity at connection time.
- **Claude MCP user** — no query syntax needed; see
  [Claude + Cube Connector](claude-cube-connector.md) and the
  [MCP example](#claude-mcp).

## Authentication

Cube resolves access from your identity — never a shared key. Requests carry an
HS256 JWT whose payload includes a top-level `email` claim; Cube resolves that
email against HR data into row- and column-level access (see
[how access is resolved](cube.md#how-access-is-resolved)).

- **Token:** an HS256 JWT signed with the deployment's API secret, payload
  `{"email": "you@apps.teamschools.org"}`.
- **Header:** `Authorization: <token>` — the raw token, **no `Bearer` prefix**.
- **Base URLs:** find the REST and SQL API URLs under **Cube Cloud → Settings →
  API Credentials** for the deployment. The MCP endpoint is configured for you
  by the connector.

No/invalid token is rejected; a valid token whose email resolves to no access
sees zero rows (default-deny).

## Query format

A REST query is a JSON object. The common keys:

| Key              | Purpose                                                                                       |
| ---------------- | --------------------------------------------------------------------------------------------- |
| `measures`       | Aggregations, dotted `<view>.<measure>` (e.g. `student_attendance_view.avg_daily_attendance`) |
| `dimensions`     | Group-by fields, dotted `<view>.<dimension>`                                                  |
| `filters`        | List of `{member, operator, values}` — see operators below                                    |
| `timeDimensions` | Date grouping/ranges: `{dimension, granularity, dateRange}`                                   |
| `order`          | `{member: "asc" \| "desc"}`                                                                   |
| `limit`          | Row cap                                                                                       |

Every member is dotted `<view>.<member>`; bare names do not resolve.

### Filter operators

Named, not SQL. Common ones: `equals`, `notEquals`, `contains`, `gt`, `gte`,
`lt`, `lte`, `set`, `notSet`, `inDateRange`, `beforeDate`, `afterDate`.
SQL-style `=` / `IN` / `LIKE` do not parse.

### Dates

For a single date use a `filters` entry with `equals`. For a range or when you
need a `granularity` (day/week/month/…), use `timeDimensions` with `dateRange`.

### Academic year

`academic_year` is the **start** year: `academic_year` 2025 means the 2025-26
school year (`academic_year_label` `"2025-2026"`, "SY26"). Prefer
`academic_year_label` when filtering — it is unambiguous.

## Error handling

- **Field outside your tier → the whole query is blocked**, not silently
  trimmed. Cube returns an error naming the hidden member; it does not drop the
  column and return the rest. Build BI workbooks from fields your least-
  privileged audience can see (SQL-API tools like Superset filter the field list
  per user at connect time and avoid this).
- **No matching reader group → zero rows** (default-deny). `/meta` also returns
  no cubes in this case — it is access-filtered, not empty.

## Examples

Each example returns network-wide average daily attendance for one academic year
— the same figure by three paths.

### REST API

```bash
tok=$(node -e "const j=require('jsonwebtoken');console.log(j.sign({email:'you@apps.teamschools.org'},process.env.CUBEJS_API_SECRET,{algorithm:'HS256'}))")
curl -s -H "Authorization: $tok" -H 'Content-Type: application/json' \
  -X POST --data '{"query":{
    "measures":["student_attendance_view.avg_daily_attendance"],
    "timeDimensions":[{"dimension":"student_attendance_view.attendance_date",
                       "dateRange":["2025-07-01","2026-06-30"]}]
  }}' \
  <REST_BASE_URL>/load
```

Replace `<REST_BASE_URL>` with the deployment's REST API base (from API
Credentials, ending in `/cubejs-api/v1`).

### SQL API

```python
import psycopg2  # connect as your email; identity resolves from the SQL user

conn = psycopg2.connect(host="<SQL_HOST>", port=<SQL_PORT>,
                        user="you@apps.teamschools.org",
                        password="<SQL_PASSWORD>", dbname="cube")
cur = conn.cursor()
cur.execute(
    "SELECT MEASURE(avg_daily_attendance) FROM student_attendance_view"
)
print(cur.fetchall())
```

### Claude MCP

Ask in plain English — no field names or SQL:

```text
What was network-wide average daily attendance for the 2025-26 school year?
```

Claude picks the Cube tool, runs the query under your identity, and returns the
answer. See [Claude + Cube Connector](claude-cube-connector.md).
