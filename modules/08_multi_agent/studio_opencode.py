"""[v2] M08 — Headless fan-out with OpenCode workers (any model). Twin of studio_claude.py.

    uv run python modules/08_multi_agent/studio_opencode.py --model ollama/qwen3.5:9b --workers 2
    uv run python modules/08_multi_agent/studio_opencode.py --model dgx/google/gemma-4-26b-it --workers 4

Difference vs studio_claude.py — and the lesson:
  `claude -p --json-schema` ENFORCES output shape inside the harness.
  `opencode run` has no schema flag -> YOUR orchestrator must extract + validate + retry.
  Harness features you relied on become code you own. Same pattern, more responsibility.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from game import Enemy, validate_json  # noqa: E402

OPENCODE = shutil.which("opencode") or "opencode"
ANGLES = ["fast fragile swarm creature", "slow armoured tank", "glass-cannon caster", "ambusher with high attack"]


def opencode_run(prompt: str, model: str, agent: str | None = None, timeout: int = 900) -> str:
    cmd = [OPENCODE, "run", "-m", model, prompt]
    if agent:
        cmd[2:2] = ["--agent", agent]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    return (r.stdout or "") + (r.stderr if r.returncode else "")


def extract_json(text: str) -> str | None:
    """Last {...} block in free text (prefers ```json fences). Crude on purpose: shows why schemas matter."""
    fences = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fences:
        return fences[-1]
    depth, start, last = 0, None, None
    for i, ch in enumerate(text):
        if ch == "{":
            depth, start = depth + 1, (i if depth == 0 else start)
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                last = text[start:i + 1]
    return last


def worker(i: int, pitch: str, model: str, retries: int = 1) -> dict:
    prompt = (f"Design ONE new Ember Crypt enemy. Theme: {pitch}. Archetype: {ANGLES[i % len(ANGLES)]}. "
              "Use ember_list_content (no id reuse; loot = existing item ids). Validate with "
              "ember_propose_entity(kind='enemy') until OK with threat 8-25. "
              "FINAL message: only the enemy JSON object in a ```json fence.")
    t0, errs = time.time(), ["no output"]
    for attempt in range(retries + 1):
        out = opencode_run(prompt if attempt == 0 else prompt + f"\nPrevious answer invalid: {errs}. Fix.", model)
        raw = extract_json(out)
        obj, errs = validate_json(Enemy, raw) if raw else (None, ["no JSON object found in output"])
        if obj:
            return {"enemy": obj.model_dump(), "secs": round(time.time() - t0), "attempts": attempt + 1}
    return {"error": errs, "secs": round(time.time() - t0), "tail": out[-400:]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pitch", default="fungal ossuary where spores animate the dead")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--model", default="ollama/qwen3.5:9b")
    a = ap.parse_args()
    if not shutil.which("opencode"):
        sys.exit("opencode not found. See modules/06b_opencode/README.md")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(lambda i: worker(i, a.pitch, a.model), range(a.workers)))
    enemies = []
    for i, r in enumerate(results):
        print(f"worker {i}: {r.get('secs')}s attempts={r.get('attempts')} -> "
              f"{r['enemy']['id'] if 'enemy' in r else 'FAIL ' + str(r['error'])[:120]}")
        if "enemy" in r:
            enemies.append(r["enemy"])
    print(f"fan-out wall time {time.time() - t0:.0f}s")

    verdict = opencode_run("Use @qa-verifier style checks on these NEW enemies as a set (distinct roles? threat spread? "
                           "on-theme?). Re-validate each with ember_propose_entity. Reply with JSON "
                           '{"verdict":"PASS|FAIL","issues":[...]}: ' + json.dumps(enemies), a.model, agent="qa-verifier")
    print("QA:", extract_json(verdict) or verdict[-300:])
    out = ROOT / "game/data/generated/enemies_opencode_studio.json"
    out.write_text(json.dumps(enemies, indent=2))
    print(f"saved {len(enemies)} -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
