"""Command line entry point.

    uv run python -m teamster.goal_setting rollout --year 2026 \
        --group nj_math_1_2 --out runs/ay2026/nj_math_1_2/$(date +%FT%H%M)
    uv run python -m teamster.goal_setting rollout ... --plan
    uv run python -m teamster.goal_setting verify-crosswalk
    uv run python -m teamster.goal_setting show --run <folder> --student <n>
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from datetime import date
from pathlib import Path

from teamster.goal_setting import (
    adapters,
    diff,
    manifest,
    outputs,
    show,
    verify_crosswalk,
)
from teamster.goal_setting.adapters import archive, goals_sheet, iready_boy, roster_sql
from teamster.goal_setting.config import ConfigError, load_crosswalk, load_rules
from teamster.goal_setting.pipeline import FreshnessError, run_group
from teamster.goal_setting.rules.invariants import InvariantError

REPO = Path(__file__).resolve().parents[3]
DEFAULT_RULES_DIR = REPO / "config" / "goal_setting"
SOURCES = {"iready_boy": iready_boy}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="teamster.goal_setting")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("rollout", help="propose school goals and buckets for one group")
    r.add_argument("--year", type=int, required=True)
    r.add_argument("--group", required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument(
        "--plan", action="store_true", help="compute, diff, check; write nothing"
    )
    r.add_argument(
        "--input", type=Path, help="replay from a prior run folder's inputs/"
    )
    r.add_argument(
        "--against", type=Path, help="prior run folder for student-depth diff"
    )
    r.add_argument(
        "--baseline-date",
        type=date.fromisoformat,
        help="pin a roster date for the freshness baseline",
    )
    r.add_argument("--force-stale", action="store_true")
    r.add_argument("--allow-reclassification", action="store_true")
    r.add_argument("--rules", type=Path)
    r.add_argument("--crosswalk", type=Path)
    r.add_argument("--manifest-dir", type=Path, default=DEFAULT_RULES_DIR / "manifests")

    v = sub.add_parser(
        "verify-crosswalk", help="check ps_programs.yaml against PowerSchool"
    )
    v.add_argument("--crosswalk", type=Path)

    s = sub.add_parser(
        "show", help="replay one student's explanation from a run folder"
    )
    s.add_argument("--run", type=Path, required=True)
    s.add_argument("--student", type=int, required=True)
    s.add_argument("--region")
    return p


def _err(msg: str) -> int:
    print(msg, file=sys.stderr)
    return 1


def _rollout(a: argparse.Namespace, client_factory) -> int:
    rules_path = a.rules or DEFAULT_RULES_DIR / f"ay{a.year}.yaml"
    xw_path = a.crosswalk or DEFAULT_RULES_DIR / "ps_programs.yaml"
    rules = load_rules(rules_path)
    xw = load_crosswalk(xw_path)
    if rules.academic_year != a.year:
        return _err(
            f"{rules_path} is for academic_year {rules.academic_year}, not {a.year}"
        )
    group = rules.group(a.group)

    client = client_factory()
    problems = verify_crosswalk.run(client, xw)
    if problems:
        return _err("crosswalk check failed:\n  " + "\n  ".join(problems))

    input_name = f"{group.source}_{group.name}.csv"
    if a.input:
        prior_manifest = diff.load_prior_manifest(a.input / "manifest.json")
        if prior_manifest is None:
            return _err(f"{a.input} has no manifest.json")
        expected = next(i for i in prior_manifest["inputs"] if i["file"] == input_name)
        rows = archive.read_input(a.input / "inputs" / input_name, expected["sha256"])
        records = archive.rows_to_records(rows)
    else:
        records = SOURCES[group.source].fetch(client, group, a.year)
        rows = archive.records_to_rows(records)

    targets = (
        goals_sheet.inline_targets(group)
        if group.target.from_ == "inline"
        else goals_sheet.fetch_targets(client, group, a.year)
    )

    manifest_path = a.manifest_dir / f"ay{a.year}" / f"{group.name}.json"
    prior = diff.load_prior_manifest(manifest_path)
    baseline = None
    if prior is not None:
        baseline = {
            (c["region"], c["school"], c["grade_level"]): c["n"]
            for i in prior["inputs"]
            for c in i["counts_by_school_grade"]
        }
    elif a.baseline_date:
        baseline = roster_sql.fetch_baseline(client, group, a.year, a.baseline_date)

    proposal = run_group(
        group, a.year, records, targets, baseline, force_stale=a.force_stale
    )

    report = diff.diff_manifests(
        prior, manifest.build(proposal, "", "", [], None, a.force_stale)
    )
    if a.against and (a.against / "student_buckets.csv").exists():
        with (a.against / "student_buckets.csv").open() as fh:
            report = diff.add_student_depth(
                report, list(csv.DictReader(fh)), proposal.records
            )

    print(report.render())
    print()
    print(outputs.summary_tables(proposal))

    if report.verdict == "reclassifies" and not a.allow_reclassification:
        print(
            "\nrefusing to write: pass --allow-reclassification to accept the "
            "transitions above",
            file=sys.stderr,
        )
        return 2
    if a.plan:
        print("\n--plan: nothing written")
        return 0

    a.out.mkdir(parents=True, exist_ok=True)
    input_meta = archive.write_input(rows, a.out / "inputs" / input_name)
    m = manifest.build(
        proposal,
        rules_sha=manifest.sha256_file(rules_path),
        crosswalk_sha=manifest.sha256_file(xw_path),
        inputs=[input_meta],
        diff=report.as_dict(),
        force_stale=a.force_stale,
    )
    written = outputs.write_run(a.out, proposal, m, xw)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.out / "manifest.json", manifest_path)
    print("\nwrote:")
    for w in written:
        print(f"  {w}")
    print(f"  {manifest_path}  (commit this one)")
    return 0


def main(argv: list[str] | None = None, client_factory=adapters.client) -> int:
    a = _parser().parse_args(argv)
    try:
        if a.cmd == "rollout":
            return _rollout(a, client_factory)
        if a.cmd == "verify-crosswalk":
            xw = load_crosswalk(a.crosswalk or DEFAULT_RULES_DIR / "ps_programs.yaml")
            problems = verify_crosswalk.run(client_factory(), xw)
            for p in problems:
                print(p)
            print("crosswalk OK" if not problems else f"{len(problems)} problems")
            return 1 if problems else 0
        if a.cmd == "show":
            for line in show.explain(a.run, a.student, a.region):
                print(line)
            return 0
    except (
        ConfigError,
        FreshnessError,
        InvariantError,
        goals_sheet.MissingTargets,
        archive.ArchiveMismatch,
        NotImplementedError,
    ) as e:
        return _err(f"{type(e).__name__}: {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
