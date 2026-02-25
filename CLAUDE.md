# Teamster – Claude Code Instructions

## dbt Model Schema Files

Whenever columns are **added or removed** from any model under
`src/dbt/kipptaf/models/extracts/`, the corresponding `.yml` properties file
in that model's `properties/` directory must be updated in the same commit:

- Add a new `- name: / data_type:` entry for every new column.
- Remove the entry for every deleted column.
- Keep entries in the same order as the `SELECT` column list in the SQL file.

The properties files live at:

```
src/dbt/kipptaf/models/extracts/<subfolder>/properties/<model_name>.yml
```
