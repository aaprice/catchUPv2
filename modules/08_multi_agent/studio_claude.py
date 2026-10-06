"""M08.2 — Same studio, but every worker is a headless Claude Code process (`claude -p`).

    uv run python modules/08_multi_agent/studio_claude.py --pitch "fungal ossuary"
    uv run python modules/08_multi_agent/studio_claude.py --pitch "fungal ossuary" --model haiku --workers 2

Why this matters: Claude Code = programmable agent runtime. Your Python = orchestrator, Claude = workers.
Each worker: own process, own context window, own tool allowlist, schema-enforced output
(`--json-schema` -> .structured_output). Workers use project MCP server `ember` (from .mcp.json) to validate.

Cost control (Pro plan): haiku for workers, sonnet for checker, small worker count, --max-turns caps.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAUDE = shutil.which("claude") or "claude"

ENEMY_SCHEMA = {"type": "object", "required": ["id", "name", "hp", "atk", "defense", "xp", "loot", "description"],
                "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "hp": {"type": "integer"},
                               "atk": {"type": "integer"}, "defense": {"type": "integer"}, "xp": {"type": "integer"},
                               "loot": {"type": "array", "items": {"type": "string"}},
                               "description": {"type": "string"}}}
VERDICT_SCHEMA = {"type": "object", "required": ["verdict", "issues"],
                  "properties": {"verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
                                 "issues": {"type": "array", "items": {"type": "string"}}}}


def claude_call(prompt: str, schema: dict, model: str, tools: str, max_turns: int = 12) -> dict:
    """One headless Claude Code agent run. Returns parsed JSON envelope."""
    cmd = [CLAUDE, "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(schema),
           "--model", model, "--max-turns", str(max_turns), "--allowedTools", tools,
           "--permission-mode", "dontAsk"]          # anything not allow-listed is denied, never prompts
    t0 = time.time()
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    try:
        env = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": (r.stdout + r.stderr)[-800:]}
    env["_secs"] = round(time.time() - t0, 1)
    return env


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pitch", default="fungal ossuary where spores animate the dead")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--checker-model", default="sonnet")
    args = ap.parse_args()
    if not shutil.which("claude"):
        sys.exit("claude CLI not found. See SETUP.md section 3.")

    angles = ["fast fragile swarm creature", "slow armoured tank", "glass-cannon caster", "ambusher with high attack"]
    worker_tools = "mcp__ember__list_content,mcp__ember__propose_entity,mcp__ember__simulate_fight"

    def worker(i: int) -> dict:
        prompt = (f"Design ONE new Ember Crypt enemy. Theme: {args.pitch}. Archetype: {angles[i % len(angles)]}. "
                  "Use mcp__ember__list_content first (no id reuse; loot must use existing item ids). "
                  "Validate with mcp__ember__propose_entity(kind='enemy') until OK with threat 8-25. "
                  "Return the final enemy as structured output.")
        return claude_call(prompt, ENEMY_SCHEMA, args.model, worker_tools)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:                    # FAN-OUT: N claude processes
        results = list(ex.map(worker, range(args.workers)))
    print(f"fan-out: {args.workers} workers in {time.time() - t0:.0f}s (wall)\n")

    enemies, total_cost = [], 0.0
    for i, r in enumerate(results):
        if "error" in r:
            print(f"worker {i}: ERROR {r['error']}")
            continue
        total_cost += r.get("total_cost_usd") or 0
        e = r.get("structured_output")
        print(f"worker {i}: {r['_secs']}s turns={r.get('num_turns')} session={r.get('session_id', '')[:8]} -> "
              f"{e and e.get('id')}")
        if e:
            enemies.append(e)

    # ---- maker-checker: independent reviewer with stronger model, read-only tools -------------
    check = claude_call(
        "You are skeptical QA for Ember Crypt. Review these NEW enemies as a set: " + json.dumps(enemies) +
        ". For each, run mcp__ember__propose_entity to re-validate and judge: distinct roles? threat spread? "
        "names/descriptions on-theme and non-duplicative? Return verdict + specific issues.",
        VERDICT_SCHEMA, args.checker_model, "mcp__ember__propose_entity,mcp__ember__list_content", max_turns=10)
    total_cost += check.get("total_cost_usd") or 0
    print(f"\nQA ({args.checker_model}): {json.dumps(check.get('structured_output'), indent=1)}")

    out = ROOT / "game/data/generated/enemies_claude_studio.json"
    out.write_text(json.dumps(enemies, indent=2))
    print(f"\nsaved {len(enemies)} enemies -> {out.relative_to(ROOT)}")
    print(f"API-equivalent cost estimate ${total_cost:.3f} (on Pro this draws from plan usage, not billed)")
    print("Resume any worker's session to ask follow-ups: claude -r <session_id>")


if __name__ == "__main__":
    main()
