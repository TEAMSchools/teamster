"""Migrate materialization history from one asset key to another.

Usage:
    uv run scripts/migrate-asset-key.py old/key/path new/key/path
    uv run scripts/migrate-asset-key.py old/key/path new/key/path --dry-run
    uv run scripts/migrate-asset-key.py old/key/path new/key/path --wipe-old

Asset keys use "/" as the separator (e.g. "kipptaf/dbt/my_model").

Caveats:
    - Migrated events are "runless" (no run association)
    - Original event timestamps are not preserved at the storage level
    - Automation condition cursors won't recognize migrated events
"""

import argparse
import sys

from dagster import AssetKey, AssetMaterialization, AssetRecordsFilter, DagsterInstance


def migrate_asset_key(
    instance: DagsterInstance,
    old_key: AssetKey,
    new_key: AssetKey,
    dry_run: bool = False,
    wipe_old: bool = False,
    batch_size: int = 100,
) -> int:
    migrated = 0
    cursor = None

    while True:
        result = instance.fetch_materializations(
            records_filter=AssetRecordsFilter(asset_key=old_key),
            limit=batch_size,
            cursor=cursor,
            ascending=True,
        )

        for record in result.records:
            mat = record.asset_materialization
            if mat is None:
                continue

            if dry_run:
                partition_str = f" partition={mat.partition}" if mat.partition else ""
                print(f"  would migrate: {record.timestamp}{partition_str}")
            else:
                instance.report_runless_asset_event(
                    AssetMaterialization(
                        asset_key=new_key,
                        metadata=mat.metadata,
                        partition=mat.partition,
                        tags=mat.tags,
                        description=mat.description,
                    )
                )

            migrated += 1

        if not result.has_more:
            break
        cursor = result.cursor

    if wipe_old and not dry_run and migrated > 0:
        instance.wipe_assets([old_key])
        print(f"wiped old key: {old_key.to_user_string()}")

    return migrated


def main():
    parser = argparse.ArgumentParser(
        description="Migrate materialization history between asset keys.",
    )
    parser.add_argument(
        "old_key", help='source asset key (e.g. "kipptaf/dbt/old_model")'
    )
    parser.add_argument(
        "new_key", help='target asset key (e.g. "kipptaf/dbt/new_model")'
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be migrated without writing",
    )
    parser.add_argument(
        "--wipe-old",
        action="store_true",
        help="wipe the old asset key after migration",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="number of events to fetch per batch (default: 100)",
    )

    args = parser.parse_args()

    old_key = AssetKey(args.old_key.split("/"))
    new_key = AssetKey(args.new_key.split("/"))

    print(
        f"{'[DRY RUN] ' if args.dry_run else ''}migrating: {old_key.to_user_string()} -> {new_key.to_user_string()}"
    )

    with DagsterInstance.get() as instance:
        if not instance.has_asset_key(old_key):
            print(
                f"error: asset key not found: {old_key.to_user_string()}",
                file=sys.stderr,
            )
            sys.exit(1)

        if instance.has_asset_key(new_key) and not args.dry_run:
            print(
                f"warning: target key already exists: {new_key.to_user_string()}",
                file=sys.stderr,
            )
            response = input("continue? [y/N] ")
            if response.lower() != "y":
                sys.exit(0)

        migrated = migrate_asset_key(
            instance=instance,
            old_key=old_key,
            new_key=new_key,
            dry_run=args.dry_run,
            wipe_old=args.wipe_old,
            batch_size=args.batch_size,
        )

    action = "would migrate" if args.dry_run else "migrated"
    print(f"{action} {migrated} materialization events")


if __name__ == "__main__":
    main()
