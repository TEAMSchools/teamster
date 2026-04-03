# PowerSchool SIS ODBC Tests

Unit tests for the PowerSchool SIS ODBC module
(`src/teamster/libraries/powerschool/sis/odbc/`). All tests are pure unit tests
using mocks — no external connections, env vars, or SSH tunnels required.

## Running

```bash
uv run pytest tests/libraries/powerschool/sis/odbc/ -v
```

## Test Files

| File                | Covers         | Key scenarios                                                                                                                                                                                                                                          |
| ------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `test_utils.py`     | `utils.py`     | `get_query_text` SQL generation, `format_oracle_timestamp` timezone handling, `get_partition_window` fiscal/monthly bounds, `powerschool_connection` lifecycle and cleanup, `evaluate_asset_staleness` for both non-partitioned and partitioned assets |
| `test_assets.py`    | `assets.py`    | `build_powerschool_table_asset` metadata wiring for partitioned and non-partitioned assets                                                                                                                                                             |
| `test_resources.py` | `resources.py` | `connect()` delegation to oracledb, `execute_query` tuple and Avro output modes, cursor tuning params                                                                                                                                                  |
| `test_schedules.py` | `schedules.py` | `build_powerschool_sis_asset_schedule` groups stale results into RunRequests by partitions def and partition key                                                                                                                                       |
| `test_sensors.py`   | `sensors.py`   | `build_powerschool_asset_sensor` groups stale results into SensorResult with job routing, empty results case                                                                                                                                           |

## Conventions

- Tests mock Dagster internals (`DagsterInstance`, `AssetsDefinition`) and
  oracledb connections — they validate orchestration logic, not database
  connectivity.
- Schedule and sensor tests access internal Dagster attributes
  (`_execution_fn.decorated_fn`, `_raw_fn`) to call the decorated function
  directly without a full Dagster instance. These are marked with
  `trunk-ignore(pyright)` comments.
