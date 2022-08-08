`query-*.yaml`

```yaml
destination:
  name: String
  type: String
  path: String*
queries:
  - sql: (choose exactly one)
      text: String
      file: String ("./teamster/local/config/datagun/sql/*.sql")
      schema:
        table: String
        columns: String*
        where: String*
    file:
      stem: String
      suffix: String
      format: Dict*
  - ...
resources:
  destination:
    config:
      # SFTP
      remote_host: StringSource
      username: StringSource
      password: StringSource
      # Google Sheets
      folder_id: String

* optional
```
