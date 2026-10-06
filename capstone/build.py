"""M10 — Capstone pipeline: pitch -> studio (multi-agent) -> forge (loop) -> gates (evals) -> play/engines.

    uv run python capstone/build.py --pitch "frost-bitten crypt wing" --name frost_wing
    uv run python capstone/build.py --pitch "..." --name x --skip-studio         # reuse existing generated content
    uv run python capstone/build.py --pitch "..." --name x --blender             # also build blockout in Blender
    uv run python capstone/build.py --pitch "..." --name x --unity               # [v2] also build in open Unity editor

This file is a WORKFLOW (code decides the steps) wrapping AGENTS (LLM decides inside each step).
That hybrid is how most production AI systems look: deterministic skeleton, agentic muscles.

    ┌ pitch ┐
    ▼       │
  [1] studio_local.py  (orchestrator + parallel workers + QA)  -> enemies_/items_/lore_*.json
  [2] level_forge.py   (gen -> verify -> critic loop)          -> generated/<name>.json
  [3] GATES (deterministic, no LLM): validator, bot playtest, balance flags  -> fail = stop pipeline
  [4] outputs: REPORT.md, play command, optional Blender / Unity build, Godot headless .tscn command
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game import ContentDB, validate_level  # noqa: E402
from game.autoplay import play  # noqa: E402
from game.balance import flags, report  # noqa: E402


def step(title: str, cmd: list[str]) -> None:
    print(f"\n\033[1m=== {title} ===\033[0m\n$ {' '.join(cmd)}")
    t0 = time.time()
    r = subprocess.run([sys.executable, *cmd], cwd=ROOT)
    print(f"--- {title}: exit {r.returncode} in {time.time() - t0:.0f}s")
    if r.returncode != 0:
        sys.exit(f"pipeline stopped at: {title}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pitch", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--skip-studio", action="store_true")
    ap.add_argument("--no-critic", action="store_true")
    ap.add_argument("--blender", action="store_true")
    ap.add_argument("--unity", action="store_true", help="[v2] build in running Unity editor (Ember bridge)")
    a = ap.parse_args()
    t0 = time.time()

    if not a.skip_studio:
        step("1. studio (multi-agent content)", ["modules/08_multi_agent/studio_local.py", "--pitch", a.pitch])
    forge_cmd = ["modules/07_loop_engineering/level_forge.py", "--include-generated", "--name", a.name, "--max-iters", "8",
                 "--brief", f"{a.pitch}. Use the NEW themed enemies/items if present. Locked door + key guardian. ~18x10."]
    if a.no_critic:
        forge_cmd.append("--no-critic")
    step("2. forge (generate-verify loop)", forge_cmd)

    # ---- 3. gates: deterministic, cheap, non-negotiable --------------------------------
    print("\n\033[1m=== 3. gates ===\033[0m")
    db = ContentDB(include_generated=True)
    if not (ROOT / "game/data/generated" / f"{a.name}.json").exists():
        sys.exit("forge produced no playable level. Read runs/*-forge.jsonl; rerun with --no-critic or bigger model.")
    lv = db.load_level(a.name)
    rep = validate_level(lv, db)
    bot = play(lv, db)
    bal = flags(report(db))
    gates = {"validator": rep.ok, "bot_wins": bot["won"], "bot_hp_margin>=5": bot["hp_left"] >= 5, "balance_flags": not bal}
    for g, ok in gates.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {g}")
    new_enemies = [e.id for e in lv.enemies if e.id not in ContentDB().enemies]

    # ---- 4. outputs ----------------------------------------------------------------------
    md = [f"# Capstone report: {lv.name}", f"pitch: *{a.pitch}*  |  built in {time.time() - t0:.0f}s", "",
          "```", *lv.map, "```", "", f"stats: {rep.stats}", f"new enemies used: {new_enemies}",
          f"bot: {json.dumps({k: bot[k] for k in ('won', 'turns', 'hp_left', 'kills')})}", f"balance flags: {bal}",
          "", "## gates", *[f"- [{'x' if ok else ' '}] {g}" for g, ok in gates.items()], "",
          f"play: `uv run python -m game.play --level {a.name}`",
          f"blender: in Claude Code: `build {a.name} in blender and render a preview`",
          f"unity: Ember > Import Level JSON > game/data/generated/{a.name}.json  (or agent: unity_build_level {a.name})",
          f"godot: godot --headless --path <proj> --script res://ember_import.gd -- <abs>/game/data/generated/{a.name}.json res://{a.name}.tscn"]
    out = ROOT / "capstone" / f"REPORT_{a.name}.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"\nreport -> {out.relative_to(ROOT)}")

    if a.blender:
        sys.path.insert(0, str(ROOT / "modules/05_mcp/blender"))
        from blender_mcp_server import blender_build_level  # direct call, no MCP needed when it's your own code
        print("blender:", blender_build_level(a.name))

    if a.unity:
        sys.path.insert(0, str(ROOT / "modules/05_mcp/unity"))
        from unity_mcp_server import unity_build_level, unity_screenshot
        print("unity:", unity_build_level(a.name))
        print("unity screenshot:", unity_screenshot(f"{a.name}_unity.png"))

    if not all(gates.values()):
        sys.exit("gates failed — see report. (Loop again, or fix by hand / with Claude Code.)")
    print(f"\n\033[32mSHIPPABLE.\033[0m  uv run python -m game.play --level {a.name}")


if __name__ == "__main__":
    main()
