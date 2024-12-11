# Pull Request

## Summary & Motivation

[//]: # "When merged, this pull request will..."

## Self-review

- [ ] Update **due date**, **assignee**, and **priority** on our
      [TEAMster Asana Project](https://app.asana.com/0/1205971774138578/1205971926225838)
- [ ] <kbd>Format</kbd> has been run on all modified files
- [ ] Ensure you are using the `union_dataset_join_clause()` macro for queries that employ any
      models using these datasets: `deanslist` `edplan` `iready` `overgrad` `pearson` `powerschool`
      `renlearn` `titan`
- [ ] If you are adding a new external source, run:

      dbt run-operation stage_external_sources --vars "ext_full_refresh: true"

  **If this is a same-day request, please flag that in our Slack channel!**

## Troubleshooting

- [SqlFluff Rules Reference](https://docs.sqlfluff.com/en/stable/rules.html)
- [Trunk](https://teamschools.github.io/teamster/CONTRIBUTING/#trunk)
- [dbt](https://teamschools.github.io/teamster/CONTRIBUTING/#dbt-cloud_1)
