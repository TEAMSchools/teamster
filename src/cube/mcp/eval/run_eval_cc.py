#!/usr/bin/env python3
"""Run the academic-year eval through the Claude Agent SDK.

Same experiment as run_eval.py (arms A/B x models x prompts x reps, scored by
scorer.py), but drives the model through Claude Code instead of the raw
Anthropic Messages API — so it authenticates with your Claude Code
subscription, no ANTHROPIC_API_KEY needed.

The agent is run HERMETIC: the arm instructions are the entire system prompt
(replace, not the claude_code preset), built-in tools are disabled (tools=[]),
and ambient MCP servers / filesystem settings are ignored (strict_mcp_config,
setting_sources=[]). This is required for a valid measurement — without it the
model leaks into Bash / ToolSearch / sub-agents and the live claude.ai Cube
connector (observed: it queried production Cube and returned pre-rename member
names). The result is the same clean "model + cube instructions + only cube
tools" surface as the API runner, just on subscription auth — NOT a faithful
reproduction of the claude.ai connector's own host prompt.

Cube tools are in-process SDK MCP tools (create_sdk_mcp_server): meta returns
the fixed catalog, load/sql return dummy results. The filter the model builds is
captured from the streamed ToolUseBlock.input, not from inside the tools.

Run it in YOUR terminal (the SDK shells out to the `claude` binary, which must
be on PATH and logged in — it is not available in the Bash sandbox):

    # ensure no metered key shadows the subscription:
    unset ANTHROPIC_API_KEY
    uv run --with claude-agent-sdk --with pyyaml \
        python src/cube/mcp/eval/run_eval_cc.py --dry-run
    uv run --with claude-agent-sdk --with pyyaml \
        python src/cube/mcp/eval/run_eval_cc.py --smoke
    uv run --with claude-agent-sdk --with pyyaml \
        python src/cube/mcp/eval/run_eval_cc.py --reps 5

Note: from 2026-06-15, subscription Agent-SDK usage draws from a separate
monthly Agent-SDK credit pool.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import arms as arms_mod  # noqa: E402
import scorer as scorer_mod  # noqa: E402
import yaml  # noqa: E402

# Claude Code model aliases (resolve to claude-sonnet-4-6 / claude-haiku-4-5).
DEFAULT_MODELS = ["sonnet", "haiku"]
DEFAULT_REPS = 5
DEFAULT_CONCURRENCY = 5  # keep small to stay under subscription rate limits
MAX_TURNS = 12
PROMPTS_PATH = Path(__file__).resolve().parent / "prompts.yaml"
DEFAULT_OUT = Path(__file__).resolve().parent / "out" / "results_cc.jsonl"

# Non-zero, internally consistent stub so the model answers in one load call.
# A zero/empty result makes the model "troubleshoot" (the instructions say
# empty results imply a missing cube-* access group), which burns turns.
_LOAD_RESULT = {
    "data": [
        {
            "student_attendance_view.count_students": "1248",
            "student_attendance_view.count_chronically_absent": "187",
            "student_attendance_view.percent_chronically_absent": "0.15",
        }
    ]
}
_SQL_RESULT = {
    "sql": {"status": "ok", "sql": ["SELECT 1", []], "query_type": "regular"}
}


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
        default=["A_baseline", "B_instructions"],
        choices=["A_baseline", "B_instructions"],
    )
    p.add_argument("--reps", type=int, default=DEFAULT_REPS)
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    p.add_argument("--limit", type=int, default=0, help="cap prompts (0 = all)")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--dry-run", action="store_true", help="no model calls")
    p.add_argument(
        "--smoke", action="store_true", help="1 prompt x B x 1 model x 1 rep"
    )
    return p.parse_args()


def _make_tools(tool_desc: dict[str, str]) -> dict[str, Any]:
    """Build in-process SDK tools; descriptions reuse the real server's text."""
    # trunk-ignore(pyright/reportMissingImports): claude-agent-sdk is a runtime --with dep
    from claude_agent_sdk import tool

    @tool("meta", tool_desc["meta"], {})
    async def meta_tool(_args: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": json.dumps(arms_mod.META_STUB)}]}

    @tool("load", tool_desc["load"], {"query": dict})
    async def load_tool(_args: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": json.dumps(_LOAD_RESULT)}]}

    @tool("sql", tool_desc["sql"], {"query": dict})
    async def sql_tool(_args: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": json.dumps(_SQL_RESULT)}]}

    return {
        "meta": meta_tool,
        "load": load_tool,
        "sql": sql_tool,
    }


def _arm_tool_names(_arm_name: str) -> list[str]:
    return ["meta", "load", "sql"]


async def run_one(
    *,
    model: str,
    instructions: str,
    sdk_server: Any,
    allowed_tools: list[str],
    prompt: str,
) -> dict[str, Any]:
    # trunk-ignore(pyright/reportMissingImports): claude-agent-sdk is a runtime --with dep
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
        query,
    )

    # Hermetic config: the arm instructions ARE the whole system prompt
    # (replace, not the claude_code preset), built-in tools are disabled, and
    # ambient MCP servers / filesystem settings are ignored. Without these the
    # model leaks into Bash / ToolSearch / the live claude.ai Cube connector
    # (allowed_tools is only permission pre-approval, NOT an availability gate).
    options = ClaudeAgentOptions(
        model=model,
        system_prompt=instructions,
        mcp_servers={"cube": sdk_server},
        allowed_tools=allowed_tools,
        tools=[],  # disable all built-in tools (Bash, ToolSearch, Task, ...)
        strict_mcp_config=True,  # ignore project .mcp.json + live connectors
        setting_sources=[],  # ignore CLAUDE.md / settings.json
        permission_mode="bypassPermissions",
        max_turns=MAX_TURNS,
    )
    load_queries: list[Any] = []
    tool_calls: list[str] = []  # every tool name, in order — to diagnose loops
    text_parts: list[str] = []
    error: str | None = None

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        tool_calls.append(block.name)
                        if block.name.endswith("__load") or block.name == "load":
                            load_queries.append(block.input.get("query"))
                    elif isinstance(block, TextBlock):
                        text_parts.append(block.text)
            elif isinstance(message, ResultMessage) and message.result:
                text_parts.append(message.result)
    except Exception as exc:  # noqa: BLE001 - record, don't crash the sweep
        error = f"{type(exc).__name__}: {exc}"

    return {
        "load_queries": load_queries,
        "tool_calls": tool_calls,
        "final_text": "\n".join(text_parts),
        "error": error,
    }


def do_dry_run(
    arm_defs: dict[str, Any], arm_names: list[str], prompts: list[dict[str, Any]]
) -> None:
    print(f"prompts: {len(prompts)}\n")
    for name in arm_names:
        arm = arm_defs[name]
        allowed = [f"mcp__cube__{n}" for n in _arm_tool_names(name)]
        print(f"=== {name} ===")
        print(f"  system-prompt (replace): {len(arm['instructions'])} chars")
        print(f"  allowed_tools: {allowed}")
    print("\nDry run only — no model calls made.")


async def sweep(
    *,
    arm_defs: dict[str, Any],
    arm_names: list[str],
    models: list[str],
    prompts: list[dict[str, Any]],
    reps: int,
    concurrency: int,
    tool_desc: dict[str, str],
    out_path: Path,
) -> list[dict[str, Any]]:
    # trunk-ignore(pyright/reportMissingImports): claude-agent-sdk is a runtime --with dep
    from claude_agent_sdk import create_sdk_mcp_server

    tools = _make_tools(tool_desc)
    # One server object per arm (stateless tools, safe to share across runs).
    arm_servers = {
        name: create_sdk_mcp_server(
            name="cube",
            version="1.0.0",
            tools=[tools[n] for n in _arm_tool_names(name)],
        )
        for name in arm_names
    }
    semaphore = asyncio.Semaphore(concurrency)

    jobs = [
        (model, arm_name, prompt, rep)
        for model in models
        for arm_name in arm_names
        for prompt in prompts
        for rep in range(reps)
    ]
    print(
        f"running {len(jobs)} conversations via Claude Agent SDK "
        f"(concurrency {concurrency})...",
        file=sys.stderr,
    )

    # Stream each record to disk as it completes (so progress is visible via
    # `wc -l` and a rate-limit abort doesn't lose finished work), and log a
    # [N/total] counter to stderr.
    total = len(jobs)
    out_fh = out_path.open("w", encoding="utf-8")
    write_lock = asyncio.Lock()
    done = 0

    async def one(
        model: str, arm_name: str, prompt: dict[str, Any], rep: int
    ) -> dict[str, Any]:
        nonlocal done
        async with semaphore:
            result = await run_one(
                model=model,
                instructions=arm_defs[arm_name]["instructions"],
                sdk_server=arm_servers[arm_name],
                allowed_tools=[f"mcp__cube__{n}" for n in _arm_tool_names(arm_name)],
                prompt=prompt["prompt"],
            )
        rec = scorer_mod.score_record(prompt, result)
        rec.update({"model": model, "arm": arm_name, "rep": rep})
        rec["final_text"] = result.get("final_text", "")
        rec["load_queries"] = result.get("load_queries", [])
        rec["tool_calls"] = result.get("tool_calls", [])
        async with write_lock:
            out_fh.write(json.dumps(rec) + "\n")
            out_fh.flush()
            done += 1
            flag = " ERR" if rec.get("error") else ""
            print(
                f"[{done}/{total}] {model}/{arm_name}/{prompt['id']}{flag}",
                file=sys.stderr,
            )
        return rec

    try:
        return await asyncio.gather(*(one(*job) for job in jobs))
    finally:
        out_fh.close()


def main() -> None:
    args = parse_args()
    server = arms_mod.load_server()
    arm_defs = arms_mod.build_arms(server)
    tool_desc = {
        t["name"]: t["description"] for t in arm_defs["B_instructions"]["tools"]
    }
    prompts = load_prompts()

    if args.smoke:
        prompts = prompts[:1]
        args.arms = ["B_instructions"]
        args.models = args.models[:1]
        args.reps = 1
    if args.limit:
        prompts = prompts[: args.limit]

    if args.dry_run:
        do_dry_run(arm_defs, args.arms, prompts)
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    records = asyncio.run(
        sweep(
            arm_defs=arm_defs,
            arm_names=args.arms,
            models=args.models,
            prompts=prompts,
            reps=args.reps,
            concurrency=args.concurrency,
            tool_desc=tool_desc,
            out_path=args.out,
        )
    )
    print(f"\nwrote {len(records)} records to {args.out}\n", file=sys.stderr)

    errors = [r for r in records if r.get("error")]
    if errors:
        print(
            f"WARNING: {len(errors)} reps errored (e.g. {errors[0]['error']})",
            file=sys.stderr,
        )

    print(scorer_mod.format_summary(scorer_mod.aggregate(records)))


if __name__ == "__main__":
    main()
