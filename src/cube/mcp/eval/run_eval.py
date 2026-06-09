#!/usr/bin/env python3
"""Run the academic-year resolver eval.

Sweeps {arm} x {model} x {prompt} x {reps}, driving each conversation through
the Anthropic tool-use loop against stubbed Cube tools, scores the captured
filter the model built, and prints a per-cell summary.

Usage (deps are not in pyproject — bring them in with uv):

    uv run --with anthropic --with pyyaml python src/cube/mcp/eval/run_eval.py --dry-run
    uv run --with anthropic --with pyyaml python src/cube/mcp/eval/run_eval.py --smoke
    uv run --with anthropic --with pyyaml python src/cube/mcp/eval/run_eval.py --reps 5

Requires ANTHROPIC_API_KEY in the environment (not needed for --dry-run).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Allow `import arms / harness / scorer` regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import arms as arms_mod  # noqa: E402
import scorer as scorer_mod  # noqa: E402
import yaml  # noqa: E402

DEFAULT_MODELS = ["claude-sonnet-4-6", "claude-haiku-4-5"]
DEFAULT_REPS = 5
DEFAULT_CONCURRENCY = 6
PROMPTS_PATH = Path(__file__).resolve().parent / "prompts.yaml"
DEFAULT_OUT = Path(__file__).resolve().parent / "out" / "results.jsonl"


def load_prompts() -> list[dict[str, Any]]:
    prompts = yaml.safe_load(PROMPTS_PATH.read_text(encoding="utf-8"))
    if not isinstance(prompts, list) or not prompts:
        raise RuntimeError(f"no prompts loaded from {PROMPTS_PATH}")
    return prompts


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    p.add_argument(
        "--arms",
        nargs="+",
        default=["A_baseline", "B_instructions", "C_tool"],
        choices=["A_baseline", "B_instructions", "C_tool"],
    )
    p.add_argument("--reps", type=int, default=DEFAULT_REPS)
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    p.add_argument("--limit", type=int, default=0, help="cap prompts (0 = all)")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print arms, tool names, and prompt count; make no API calls",
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help="1 prompt x 1 arm x 1 model x 1 rep, to verify wiring",
    )
    return p.parse_args()


def do_dry_run(arms: dict[str, dict[str, Any]], prompts: list[dict[str, Any]]) -> None:
    print(
        f"prompts: {len(prompts)} "
        f"(family1={sum(p['family'] == 1 for p in prompts)}, "
        f"family2={sum(p['family'] == 2 for p in prompts)}, "
        f"family3={sum(p['family'] == 3 for p in prompts)})\n"
    )
    for name, arm in arms.items():
        tool_names = [t["name"] for t in arm["tools"]]
        has_required = "REQUIRED: Before building" in arm["instructions"]
        has_crosswalk = "resolve it yourself" in arm["instructions"]
        print(f"=== {name} ===")
        print(f"  tools: {tool_names}")
        print(
            f"  instructions: {len(arm['instructions'])} chars "
            f"(REQUIRED paragraph: {has_required}; inline crosswalk: "
            f"{has_crosswalk})"
        )
    print("\nDry run only — no API calls made.")


async def sweep(
    *,
    arms: dict[str, dict[str, Any]],
    arm_names: list[str],
    models: list[str],
    prompts: list[dict[str, Any]],
    reps: int,
    concurrency: int,
    server: Any,
) -> list[dict[str, Any]]:
    import harness as harness_mod

    # trunk-ignore(pyright/reportMissingImports): anthropic is a runtime --with dep, not in pyproject
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    semaphore = asyncio.Semaphore(concurrency)

    jobs: list[tuple[str, str, dict[str, Any], int]] = [
        (model, arm_name, prompt, rep)
        for model in models
        for arm_name in arm_names
        for prompt in prompts
        for rep in range(reps)
    ]
    print(
        f"running {len(jobs)} conversations "
        f"({len(models)} models x {len(arm_names)} arms x {len(prompts)} "
        f"prompts x {reps} reps) at concurrency {concurrency}...",
        file=sys.stderr,
    )

    async def one(model: str, arm_name: str, prompt: dict[str, Any], rep: int):
        arm = arms[arm_name]
        result = await harness_mod.run_cell(
            client,
            semaphore=semaphore,
            model=model,
            instructions=arm["instructions"],
            tools=arm["tools"],
            prompt=prompt["prompt"],
            server=server,
        )
        rec = scorer_mod.score_record(prompt, result)
        rec.update({"model": model, "arm": arm_name, "rep": rep})
        rec["final_text"] = result.get("final_text", "")
        return rec

    return await asyncio.gather(*(one(*job) for job in jobs))


def main() -> None:
    args = parse_args()
    server = arms_mod.load_server()
    arms = arms_mod.build_arms(server)
    prompts = load_prompts()

    if args.smoke:
        prompts = prompts[:1]
        args.arms = ["C_tool"]
        args.models = args.models[:1]
        args.reps = 1

    if args.limit:
        prompts = prompts[: args.limit]

    if args.dry_run:
        do_dry_run({k: arms[k] for k in args.arms}, prompts)
        return

    records = asyncio.run(
        sweep(
            arms=arms,
            arm_names=args.arms,
            models=args.models,
            prompts=prompts,
            reps=args.reps,
            concurrency=args.concurrency,
            server=server,
        )
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    print(f"\nwrote {len(records)} records to {args.out}\n", file=sys.stderr)

    errors = [r for r in records if r.get("error")]
    if errors:
        print(
            f"WARNING: {len(errors)} reps errored (e.g. {errors[0]['error']})",
            file=sys.stderr,
        )

    summary = scorer_mod.aggregate(records)
    print(scorer_mod.format_summary(summary))


if __name__ == "__main__":
    main()
