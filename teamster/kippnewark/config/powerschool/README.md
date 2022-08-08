`query-*.yaml`

```yaml
execution:
  config:
    multiprocess:
      max_concurrent: int
ops:
  compose_queries:
    config:
      year_id: IntSource
      tables:
      - name: String
        queries:
          - projection: String
            q: String |
              selector: String
              value: Any
              max_value: Any
```
