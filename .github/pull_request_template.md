# Pull Request

## Summary & Motivation

[//]: # "When merged, this pull request will..."

## Self-review

### General

- [ ] If this is a same-day request, please flag that in the #data-team Slack
- [ ] Update **due date** and **assignee** on the
      [TEAMster Asana Project](https://app.asana.com/0/1205971774138578/1205971926225838)
- [ ] Run <kbd>Format</kbd> on all modified files

### dbt

- [ ] Include a corresponding `[model name].yml` properties file for all models:

      models:
        - name: [model name]
          config:
            contract:  # optional
              enforced: true
          columns:  # optional, unless using a contract
            - name: ...
              data_type: ...
              data_tests:  # column tests, optional
                - ...
          data_tests:  # model tests, optional
            - ...

- [ ] Include (or update) an
      [exposure](https://docs.getdbt.com/reference/exposure-properties) for all
      models that will be consumed by a dashboard, analysis, or application:

      exposures:
        - name: [exposure name, snake_case]
          label: [exposure name, Title Case]
          type: dashboard | notebook | analysis | ml | application
          owner:
            name: Data Team
          depends_on:
            - ref("[model name]")
          url: ...  # optional
          meta:
            dagster:
              kinds:
                - tableau | googlesheets | ...

[Dagster "kinds" Reference](https://docs.dagster.io/guides/build/assets/metadata-and-tags/kind-tags#supported-icons)

### SQL

- [ ] Use the `union_dataset_join_clause()` macro for queries that employ models
      that use regional datasets
- [ ] Do not use `group by` without any aggregations when you mean to use
      `distinct`
- [ ] All `distinct` usage must be accompanied by an comment explaining it's
      necessity
- [ ] If you are adding a new external source, before building, run:

      dbt run-operation stage_external_sources --vars "{'ext_full_refresh': 'true'}" --args select: [model name(s)]

## Troubleshooting

- [SqlFluff Rules Reference](https://docs.sqlfluff.com/en/stable/rules.html)
- [Trunk](https://teamschools.github.io/teamster/CONTRIBUTING/#trunk)
- [dbt](https://teamschools.github.io/teamster/CONTRIBUTING/#dbt-cloud_1)
