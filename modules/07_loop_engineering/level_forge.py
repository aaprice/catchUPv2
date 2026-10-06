"""M07.1 — Level Forge: generator -> verifier stack -> feedback -> retry, with explicit stop conditions.

    uv run python modules/07_loop_engineering/level_forge.py --brief "flooded ossuary with a locked door" --name flooded
    uv run python modules/07_loop_engineering/level_forge.py --brief "tiny rat warren" --context accumulate
    uv run python modules/07_loop_engineering/level_forge.py --brief "..." --no-critic --max-iters 10

Verifier stack (cheap+certain FIRST, expensive+fuzzy LAST):
  V1 schema   pydantic                 free, certain
  V2 rules    game.level.validate      free, certain   (solvable, budget, placements)
  V3 playtest game.autoplay bot        ~free, certain  (beatable, hp margin)
  V4 critic   LLM judge w/ rubric      $$, fuzzy       (fun, theme, pacing)

Context strategies:
  fresh      each iteration = brief + LAST attempt + feedback only   (Ralph-style; no context rot)
  accumulate full conversation of all attempts                       (more memory, more rot/tokens)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from game import ContentDB, Level, validate_json, validate_level  # noqa: E402
from game.autoplay import play  # noqa: E402
from lib import Tracer, get_llm  # noqa: E402

db = ContentDB()
EXAMPLE = {"name": "Rat Nest", "theme": "damp ossuary", "threat_budget": 30,
           "map": ["##########", "#@...#...#", "#.##.#.#.#", "#....D.#>#", "##########"],
           "enemies": [{"id": "crypt_rat", "x": 6, "y": 1}], "items": [{"id": "iron_key", "x": 1, "y": 3}]}

def build_gen_system(db: ContentDB) -> str:
    return f"""You design levels for grid roguelike Ember Crypt. Output ONE JSON object (Level schema).
Map legend: # wall, . floor, @ start (exactly 1), > exit (exactly 1), D locked door (needs iron_key placed on floor before it).
All rows SAME length. Border all '#'. Placements use x=column, y=row (0-based) and must sit on '.' cells.
Enemies: {{{', '.join(f'{e.id}: threat {e.threat}' for e in db.enemies.values())}}}
Items: {', '.join(db.items)}
Sum of enemy threat must be <= threat_budget. Tiny valid example:
{json.dumps(EXAMPLE)}"""


GEN_SYSTEM = build_gen_system(db)

CRITIC_SYSTEM = """You are a harsh roguelike level critic. Score 1-10 each: layout (interesting routes, no pointless
dead ends), pacing (threat rises toward exit, loot before hard fights), theme (names/layout fit brief).
Return JSON: {"layout":n,"pacing":n,"theme":n,"overall":n,"fixes":["specific actionable change", ...]}"""
CRITIC_SCHEMA = {"type": "object", "required": ["layout", "pacing", "theme", "overall", "fixes"], "properties": {
    "layout": {"type": "integer"}, "pacing": {"type": "integer"}, "theme": {"type": "integer"},
    "overall": {"type": "integer"}, "fixes": {"type": "array", "items": {"type": "string"}}}}


def verify(raw: str, use_critic: bool, critic_llm, brief: str, tr: Tracer) -> tuple[bool, list[str], dict]:
    """Run verifier stack; stop at first failing layer (no point critiquing an unsolvable level)."""
    lv, errs = validate_json(Level, raw)
    if errs:
        return False, [f"[schema] {e}" for e in errs], {"stage": "schema", "score": 0}
    rep = validate_level(lv, db)
    if not rep.ok:
        return False, [f"[rules] {e}" for e in rep.errors], {"stage": "rules", "score": 1, **rep.stats}
    pt = play(lv, db)
    if not pt["won"] or pt["hp_left"] < 5:
        why = "bot got stuck" if pt["stuck"] else f"bot died ({pt['last_log']})" if pt["dead"] else f"hp_left {pt['hp_left']} < 5"
        return False, [f"[playtest] not beatable by greedy bot: {why}. Make it easier or add potions/gear earlier."], \
            {"stage": "playtest", "score": 2, **rep.stats}
    stats = {"stage": "playtest-ok", "score": 3, **rep.stats, "bot_turns": pt["turns"], "bot_hp": pt["hp_left"]}
    if not use_critic:
        return True, [f"[warn] {w}" for w in rep.warnings], stats
    c = critic_llm.chat([{"role": "system", "content": CRITIC_SYSTEM},
                         {"role": "user", "content": f"Brief: {brief}\nLevel:\n" + "\n".join(lv.map) +
                          f"\nEnemies: {[e.model_dump() for e in lv.enemies]}\nItems: {[i.model_dump() for i in lv.items]}"
                          f"\nBot playtest: {pt['turns']} turns, {pt['hp_left']} hp left."}],
                        schema=CRITIC_SCHEMA, temperature=0.0)
    try:
        crit = json.loads(c.text)
    except json.JSONDecodeError:
        crit = {"overall": 0, "fixes": ["critic output unparseable"]}
    tr.event("info", msg=f"critic: {crit}")
    stats.update(stage="critic", score=3 + crit.get("overall", 0) / 10, critic=crit)
    if crit.get("overall", 0) >= 7:
        return True, [], stats
    return False, [f"[critic {crit.get('overall')}/10] {f}" for f in crit.get("fixes", [])[:4]], stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", default="smouldering catacomb, ~16x9, 3 enemies, locked door guarded by an ash_skeleton")
    ap.add_argument("--name", default="forged")
    ap.add_argument("--max-iters", type=int, default=6)
    ap.add_argument("--context", choices=["fresh", "accumulate"], default="fresh")
    ap.add_argument("--no-critic", action="store_true")
    ap.add_argument("--critic-model", help="different model as critic (reduces self-grading bias)")
    ap.add_argument("--token-budget", type=int, default=120_000)
    ap.add_argument("--include-generated", action="store_true", help="allow agent-made enemies/items (M08/M10)")
    args = ap.parse_args()
    global db, GEN_SYSTEM
    if args.include_generated:
        db = ContentDB(include_generated=True)
        GEN_SYSTEM = build_gen_system(db)

    gen = get_llm()
    critic = get_llm(model=args.critic_model) if args.critic_model else gen
    tr = Tracer("forge")
    schema = Level.model_json_schema()
    history: list[dict] = []
    last_raw, feedback = "", []
    best = (-1.0, None, None)
    seen_errors: list[frozenset] = []
    t0 = time.time()

    for it in range(1, args.max_iters + 1):
        task = f"Brief: {args.brief}"
        if args.context == "fresh" and last_raw:
            msgs = [{"role": "system", "content": GEN_SYSTEM},
                    {"role": "user", "content": f"{task}\n\nYour previous attempt:\n{last_raw}\n\nIt FAILED verification:\n- "
                                                + "\n- ".join(feedback) + "\nOutput a corrected full level JSON."}]
        elif args.context == "accumulate" and history:
            history.append({"role": "user", "content": "FAILED verification:\n- " + "\n- ".join(feedback) + "\nFix it."})
            msgs = [{"role": "system", "content": GEN_SYSTEM}, *history]
        else:
            msgs = [{"role": "system", "content": GEN_SYSTEM}, {"role": "user", "content": task}]
            history = msgs[1:]

        temp = 0.8 if it == 1 else 0.4
        if len(seen_errors) >= 2 and seen_errors[-1] == seen_errors[-2]:
            temp = 1.0                                      # no-progress detector: shake it up
            tr.event("loop", msg="same errors twice -> raising temperature to escape rut")
        r = gen.chat(msgs, schema=schema, temperature=temp)
        last_raw = r.text
        if args.context == "accumulate":
            history.append({"role": "assistant", "content": r.text})

        ok, feedback, stats = verify(r.text, not args.no_critic, critic, args.brief, tr)
        seen_errors.append(frozenset(f.split("]")[0] for f in feedback))
        tr.event("loop", msg=f"iter {it}: {'PASS' if ok else 'FAIL'} stage={stats['stage']} "
                             f"score={stats['score']:.2f} feedback={feedback[:3]}")
        if stats["score"] > best[0]:
            best = (stats["score"], r.text, stats)
        used = gen.total_usage["in"] + gen.total_usage["out"]
        if ok:
            break
        if used > args.token_budget:                         # budget stop condition
            tr.event("loop", msg=f"token budget hit ({used})")
            break

    score, raw, stats = best
    print(f"\n== forge done: {it} iters, {time.time() - t0:.0f}s, tokens {gen.total_usage}, best stage={stats and stats['stage']}")
    if raw and stats and stats["score"] >= 3:
        lv = Level(**json.loads(raw))
        out = ROOT / "game/data/generated" / f"{args.name}.json"
        out.write_text(lv.model_dump_json(indent=2), encoding="utf-8")
        print("\n".join(lv.map))
        print(f"saved {out.relative_to(ROOT)}  ->  uv run python -m game.play --level {args.name}")
    else:
        print("no playable level produced. Read the trace in runs/ — which verifier stage blocked most?")


if __name__ == "__main__":
    main()
