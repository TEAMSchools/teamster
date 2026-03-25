from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path

# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///


sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.dbt_yml_utils import (  # trunk-ignore(pyright/reportMissingImports): runtime sys.path insert
    find_first_select,
    find_yml_path,
    parse_select_columns,
    query_column_types,
    resolve_schema,
    strip_jinja,
    sync_yml,
)
from watchdog.events import FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]

logging.basicConfig(
    format="%(asctime)s [yml-sync] %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
log = logging.getLogger("yml-sync")

# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------

_DEBOUNCE_SECONDS = 1.0


class ExtractsSqlHandler(PatternMatchingEventHandler):
    """Watch for SQL file saves in extracts directories and sync the YML."""

    def __init__(self) -> None:
        super().__init__(
            patterns=["*.sql"], ignore_directories=True, case_sensitive=False
        )
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # watchdog callbacks
    # ------------------------------------------------------------------

    def on_modified(self, event: FileSystemEvent) -> None:
        self._schedule(str(event.src_path))

    def on_created(self, event: FileSystemEvent) -> None:
        self._schedule(str(event.src_path))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _schedule(self, path: str) -> None:
        """Debounce rapid save events — fire _process after a 1-second quiet window."""
        with self._lock:
            existing = self._timers.pop(path, None)
            if existing is not None:
                existing.cancel()
            timer = threading.Timer(_DEBOUNCE_SECONDS, self._process, args=(path,))
            self._timers[path] = timer
            timer.start()

    def _process(self, path: str) -> None:
        with self._lock:
            self._timers.pop(path, None)

        sql_path = Path(path)
        try:
            self._sync(sql_path)
        except Exception as exc:
            log.error("Unhandled error processing %s: %s", sql_path, exc)

    def _sync(self, sql_path: Path) -> None:
        yml_path = find_yml_path(sql_path)

        if not yml_path.exists():
            log.info(
                "No YML for %s — skipping (new files handled at commit time)",
                sql_path.name,
            )
            return

        log.info("Detected save: %s", sql_path.relative_to(REPO_ROOT))

        sql_text = sql_path.read_text(encoding="utf-8")

        try:
            stripped = strip_jinja(sql_text)
            body = find_first_select(stripped)
            sql_columns = parse_select_columns(body)
        except ValueError as exc:
            log.warning("Could not parse SQL in %s: %s", sql_path.name, exc)
            return

        if not sql_columns:
            log.warning("No columns found in %s — skipping", sql_path.name)
            return

        try:
            rel_path = sql_path.relative_to(REPO_ROOT)
            schema = resolve_schema(rel_path, repo_root=REPO_ROOT)
        except Exception as exc:
            log.warning("Could not resolve schema for %s: %s", sql_path.name, exc)
            return

        model_name = sql_path.stem
        log.info("Querying BQ for %s.%s column types", schema, model_name)
        bq_types = query_column_types(model_name, schema)

        sync_yml(yml_path, sql_columns, bq_types)
        log.info(
            "Synced %s (%d columns)", yml_path.relative_to(REPO_ROOT), len(sql_columns)
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    extracts_dirs = sorted(
        p for p in (REPO_ROOT / "src" / "dbt").glob("*/models/extracts") if p.is_dir()
    )

    if not extracts_dirs:
        log.error(
            "No extracts directories found under src/dbt/*/models/extracts — exiting"
        )
        sys.exit(1)

    observer = Observer()
    handler = ExtractsSqlHandler()

    for extracts_dir in extracts_dirs:
        observer.schedule(handler, str(extracts_dir), recursive=True)
        log.info("Watching %s", extracts_dir.relative_to(REPO_ROOT))

    observer.start()
    log.info("YML sync watcher running — press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        log.info("Watcher stopped")


if __name__ == "__main__":
    main()
