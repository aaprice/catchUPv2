"""M08.1 — "Content studio": multi-agent pipeline on YOUR harness + local model.

    uv run python modules/08_multi_agent/studio_local.py --pitch "frost-bitten crypt wing"
    uv run python modules/08_multi_agent/studio_local.py --pitch "fungal ossuary" --sequential   # compare wall time

Topology (orchestrator-workers + pipeline + maker-checker):

    Director (plan JSON)
        ├─► enemy_designer #1 ─┐
        ├─► enemy_designer #2 ─┼─ PARALLEL (fan-out) ─► blackboard ─► lore_writer ─► QA checker ─► integrate
        └─► item_designer   ───┘                                     (stage 2)       │ FAIL
                 ▲                                                                     │
                 └───────────────────── repair round w/ QA issues ◄────────────────────┘

Each worker = own Agent, own context, own tools. Hands results back via a `submit_*` TOOL
(structured handoff), never via free text the orchestrator must parse.

Tip: Ollama serves requests one-at-a-time by default. For real parallelism set env OLLAMA_NUM_PARALLEL=3
(more VRAM) and restart Ollama. Otherwise "parallel" just queues — measure it!
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from game import ContentDB, Enemy, Item, validate_json  # noqa: E402
from game.world import simulate_fight  # noqa: E402
from lib import Agent, Tracer, get_llm, tool  # noqa: E402

db = ContentDB()
board = {"enemies": [], "items": [], "lore": [], "verdict": None}   # shared blackboard
lock = threading.Lock()
POLICY = lambda t, c: "allow"  # noqa: E731  (unattended workers: tools are sandboxed to in-memory board)

PLAN_SCHEMA = {"type": "object", "required": ["theme", "tasks"], "properties": {
    "theme": {"type": "string"},
    "tasks": {"type": "array", "minItems": 2, "maxItems": 4, "items": {
        "type": "object", "required": ["role", "brief"], "properties": {
            "role": {"type": "string", "enum": ["enemy_designer", "item_designer"]},
            "brief": {"type": "string"}}}}}}


# ------------------------------------------------------------------ worker tool sets
def enemy_tools():
    @tool
    def list_content() -> str:
        """Existing enemy + item ids with stats. Don't reuse ids. Loot must use existing item ids."""
        return json.dumps({"enemies": {e.id: e.threat for e in db.enemies.values()},
                           "items": {i.id: i.kind for i in db.items.values()}})

    @tool
    def test_enemy(enemy_json: str) -> str:
        """Validate enemy JSON and simulate fights (starter rusty_sword vs best ember_blade, bone_shield).

        Args:
            enemy_json: JSON object with id,name,hp,atk,defense,xp,loot,description
        """
        e, errs = validate_json(Enemy, enemy_json)
        if errs:
            return "INVALID: " + "; ".join(errs)
        if e.id in db.enemies:
            return f"INVALID: id {e.id} exists"
        bad = [x for x in e.loot if x not in db.items]
        if bad:
            return f"INVALID: loot ids not found {bad}"
        starter = simulate_fight(6, 3, 30, e)
        best = simulate_fight(9, 3, 30, e)
        return json.dumps({"threat": e.threat, "starter_gear": starter, "best_gear": best,
                           "target": "threat 8-25; survivable with best gear"})

    @tool(read_only=False)
    def submit_enemy(enemy_json: str) -> str:
        """FINAL handoff. Submit your finished enemy. Call exactly once when test_enemy looks good.

        Args:
            enemy_json: the final enemy JSON object
        """
        e, errs = validate_json(Enemy, enemy_json)
        if errs:
            return "REJECTED: " + "; ".join(errs)
        with lock:
            board["enemies"] = [x for x in board["enemies"] if x["id"] != e.id] + [e.model_dump()]
        return "ACCEPTED. You are done; reply with one line summary."

    return [list_content, test_enemy, submit_enemy]


def item_tools():
    @tool
    def list_items() -> str:
        """Existing items (don't reuse ids)."""
        return json.dumps({i.id: f"{i.kind} pow{i.power} {i.value}g" for i in db.items.values()})

    @tool(read_only=False)
    def submit_item(item_json: str) -> str:
        """FINAL handoff: submit finished item. Rules: weapon/armor value >= power*8; potion power 1..6.

        Args:
            item_json: JSON object with id,name,kind,power,value,description
        """
        it, errs = validate_json(Item, item_json)
        if errs:
            return "REJECTED: " + "; ".join(errs)
        if it.id in db.items:
            return f"REJECTED: id {it.id} exists"
        if it.kind in ("weapon", "armor") and it.value < it.power * 8:
            return f"REJECTED: value must be >= {it.power * 8}"
        with lock:
            board["items"] = [x for x in board["items"] if x["id"] != it.id] + [it.model_dump()]
        return "ACCEPTED. You are done; reply with one line summary."

    return [list_items, submit_item]


def lore_tools():
    @tool
    def read_existing_lore() -> str:
        """All existing lore (must stay consistent with it)."""
        return "\n\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "game/data/lore").glob("*.md")))

    @tool(read_only=False)
    def submit_lore(markdown: str) -> str:
        """FINAL handoff: lore markdown (title + 4-8 sentences) mentioning every new enemy and item by name.

        Args:
            markdown: the lore text
        """
        with lock:
            board["lore"] = [markdown]
        return "ACCEPTED. Done."

    return [read_existing_lore, submit_lore]


def qa_tools():
    @tool
    def get_package() -> str:
        """Everything the studio produced so far."""
        with lock:
            return json.dumps({k: board[k] for k in ("enemies", "items", "lore")}, indent=1)

    @tool
    def fight(enemy_id: str, weapon_power: int, armor_power: int) -> str:
        """Simulate base player (atk4 def1 hp30) + weapon/armor power vs a NEW enemy from the package.

        Args:
            enemy_id: id of new enemy
            weapon_power: weapon power bonus (0, 2 starter, 5 best)
            armor_power: armor power bonus (0, 2, 4)
        """
        e = next((Enemy(**x) for x in board["enemies"] if x["id"] == enemy_id), None)
        return json.dumps(simulate_fight(4 + weapon_power, 1 + armor_power, 30, e)) if e else "unknown enemy"

    @tool(read_only=False)
    def submit_verdict(verdict: str, issues: list[str]) -> str:
        """FINAL: verdict 'PASS' or 'FAIL' plus specific issues, each prefixed with the role to fix
        (e.g. 'enemy_designer: frost_ghoul unbeatable even with best gear').

        Args:
            verdict: PASS or FAIL
            issues: list of actionable issues
        """
        with lock:
            board["verdict"] = {"verdict": verdict.upper(), "issues": issues}
        return "RECORDED."

    return [get_package, fight, submit_verdict]


ROLE_SETUP = {
    "enemy_designer": ("You design ONE enemy for Ember Crypt. Workflow: list_content -> draft -> test_enemy -> adjust "
                       "until threat 8-25 and survivable with best gear -> submit_enemy.", enemy_tools),
    "item_designer": ("You design ONE item for Ember Crypt. list_items -> draft -> submit_item (fix if rejected).", item_tools),
}


def run_worker(llm, role: str, brief: str, idx: int) -> str:
    system, toolset = ROLE_SETUP[role]
    agent = Agent(llm, system, toolset(), name=f"{role}#{idx}", max_turns=10, policy=POLICY,
                  tracer=Tracer(f"{role}{idx}", verbose=True))
    return agent.run(f"Theme: {board.get('theme')}. Brief: {brief}").text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pitch", default="frost-bitten crypt wing where the Long Winter never ended")
    ap.add_argument("--sequential", action="store_true")
    args = ap.parse_args()
    llm = get_llm()
    t0 = time.time()

    # ---- 1. Director: plan (structured output, no tools) -----------------------------
    plan = json.loads(llm.chat([
        {"role": "system", "content": "You are creative director of a tiny roguelike studio. Split the pitch into 2-4 "
                                      "parallel tasks for enemy_designer / item_designer. Each brief: concrete, distinct."},
        {"role": "user", "content": f"Pitch: {args.pitch}"}], schema=PLAN_SCHEMA, temperature=0.7).text)
    board["theme"] = plan["theme"]
    print(f"\nDIRECTOR PLAN: {json.dumps(plan, indent=1)}\n")

    def dispatch(tasks):
        if args.sequential:
            return [run_worker(llm, t["role"], t["brief"], i) for i, t in enumerate(tasks)]
        with ThreadPoolExecutor(max_workers=4) as ex:              # FAN-OUT
            return list(ex.map(lambda p: run_worker(llm, p[1]["role"], p[1]["brief"], p[0]), enumerate(tasks)))

    dispatch(plan["tasks"])                                          # FAN-IN at blackboard
    t_stage1 = time.time() - t0

    # ---- 2. Lore writer (pipeline stage; depends on stage-1 outputs) ---------------
    Agent(llm, "You are Ember Crypt lore writer. Read existing lore, then write lore introducing the new content. "
               "Never contradict existing lore.", lore_tools(), name="lore", max_turns=6, policy=POLICY
          ).run(f"New content: {json.dumps({k: board[k] for k in ('enemies', 'items')})}")

    # ---- 3. QA checker + 1 repair round (maker-checker) -----------------------------
    for round_ in (1, 2):
        board["verdict"] = None
        Agent(llm, "You are skeptical QA. Verify the package: each new enemy beatable with weapon_power 5 + armor_power 2 "
                   "and not trivial (hp_lost > 0) with weapon_power 2; lore mentions every new enemy+item by name; "
                   "no contradictions. Use tools, then submit_verdict.", qa_tools(), name=f"qa{round_}",
              max_turns=10, policy=POLICY, temperature=0.0).run("Verify the package.")
        v = board["verdict"] or {"verdict": "FAIL", "issues": ["QA never submitted verdict"]}
        print(f"\nQA round {round_}: {v}")
        if v["verdict"] == "PASS" or round_ == 2:
            break
        fix_tasks = [{"role": r, "brief": f"Fix this QA issue: {i}"} for i in v["issues"]
                     for r in ROLE_SETUP if i.lower().startswith(r)]
        if not fix_tasks:
            break
        dispatch(fix_tasks)

    # ---- 4. Integrate ------------------------------------------------------------------
    slug = re.sub(r"[^a-z0-9]+", "_", board["theme"].lower()).strip("_")[:24] or "studio"
    gen = ROOT / "game/data/generated"
    if board["enemies"]:
        (gen / f"enemies_{slug}.json").write_text(json.dumps(board["enemies"], indent=2))
    if board["items"]:
        (gen / f"items_{slug}.json").write_text(json.dumps(board["items"], indent=2))
    if board["lore"]:
        (gen / f"lore_{slug}.md").write_text(board["lore"][0])
    print(f"\nSTUDIO DONE in {time.time() - t0:.0f}s (stage-1 fan-out {t_stage1:.0f}s, "
          f"{'sequential' if args.sequential else 'parallel'}). tokens={llm.total_usage}")
    print(f"enemies={[e['id'] for e in board['enemies']]} items={[i['id'] for i in board['items']]} "
          f"verdict={board['verdict'] and board['verdict']['verdict']}")
    print(f"files: game/data/generated/*_{slug}.*   (ContentDB(include_generated=True) loads them)")


if __name__ == "__main__":
    main()
