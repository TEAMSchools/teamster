"""Model-in-the-loop runner: drive one prompt through the Anthropic tool-use
loop against a single arm, capturing what the model did.

Every Cube tool is stubbed so the only thing measured is model behavior:
- ``meta`` returns the fixed catalog (arms.META_STUB),
- ``load`` / ``sql`` record the query the model built and return a dummy
  result,
- ``resolve_academic_year`` (arm C only) calls the real parser in server.py.

The recorded transcript (resolver calls, load queries, final text) is handed
to scorer.py.
"""

import asyncio
import json
from types import ModuleType
from typing import Any

import arms as arms_mod

# trunk-ignore(pyright/reportMissingImports): anthropic is a runtime --with dep, not in pyproject
from anthropic import AsyncAnthropic

MAX_TOKENS = 1024
MAX_TURNS = 8


def _dispatch(
    name: str,
    tool_input: dict[str, Any],
    captured: dict[str, list[Any]],
    server: ModuleType,
) -> dict[str, Any]:
    """Execute a stubbed tool call and record arguments of interest."""
    if name == "meta":
        return arms_mod.META_STUB
    if name == "load":
        captured["load_queries"].append(tool_input.get("query"))
        # Minimal well-formed aggregate result so the model stops and answers.
        return {
            "data": [{"student_attendance_summary.count_students": "0"}],
            "annotation": {},
        }
    if name == "sql":
        captured["sql_queries"].append(tool_input.get("query"))
        return {
            "sql": {"status": "ok", "sql": ["SELECT 1", []], "query_type": "regular"}
        }
    if name == "resolve_academic_year":
        raw = str(tool_input.get("raw", ""))
        captured["resolve_calls"].append(raw)
        try:
            return dict(server._resolve_academic_year(raw))
        except ValueError as exc:
            return {"error": str(exc)}
    return {"error": f"unknown tool {name}"}


def _assistant_blocks(content: list[Any]) -> list[dict[str, Any]]:
    """Re-serialize response content blocks for the next request's history."""
    blocks: list[dict[str, Any]] = []
    for b in content:
        if b.type == "text":
            blocks.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            blocks.append(
                {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
            )
    return blocks


async def run_one(
    client: AsyncAnthropic,
    *,
    model: str,
    instructions: str,
    tools: list[dict[str, Any]],
    prompt: str,
    server: ModuleType,
) -> dict[str, Any]:
    """Run a single conversation; return the captured transcript summary."""
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    captured: dict[str, list[Any]] = {
        "resolve_calls": [],
        "load_queries": [],
        "sql_queries": [],
    }
    text_parts: list[str] = []
    error: str | None = None

    for _ in range(MAX_TURNS):
        try:
            resp = await client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=instructions,
                tools=tools,
                messages=messages,
            )
        except Exception as exc:  # noqa: BLE001 - record, don't crash the sweep
            error = f"{type(exc).__name__}: {exc}"
            break

        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        text_parts.extend(b.text for b in resp.content if b.type == "text")

        if resp.stop_reason != "tool_use" or not tool_uses:
            break

        messages.append(
            {"role": "assistant", "content": _assistant_blocks(resp.content)}
        )
        results = [
            {
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(_dispatch(tu.name, tu.input, captured, server)),
            }
            for tu in tool_uses
        ]
        messages.append({"role": "user", "content": results})

    return {
        "final_text": "\n".join(text_parts),
        "error": error,
        **captured,
    }


async def run_cell(
    client: AsyncAnthropic,
    *,
    semaphore: asyncio.Semaphore,
    **kwargs: Any,
) -> dict[str, Any]:
    """run_one under a concurrency gate."""
    async with semaphore:
        return await run_one(client, **kwargs)
