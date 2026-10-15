"""Command line: plan, run, answers, analyze, close."""

from __future__ import annotations

import argparse

COMMANDS = ("plan", "run", "answers", "analyze", "close")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cube_validate")
    sub = p.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        s = sub.add_parser(name)
        s.add_argument("checks", help="path to checks/<dashboard>.yml")
        s.add_argument("--snapshot", help="snapshot folder (default: newest)")
        s.add_argument(
            "--period",
            help="START:END dates to capture, e.g. 2025-07-01:2026-06-30",
        )
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    raise NotImplementedError(args.command)  # replaced in Task 13
