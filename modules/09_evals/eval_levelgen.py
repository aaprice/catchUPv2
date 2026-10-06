"""M09.2 — Eval level generation: single-shot validity funnel across N samples, two prompt variants.

    uv run python modules/09_evals/eval_levelgen.py --n 10
    uv run python modules/09_evals/eval_levelgen.py --n 10 --variant no_example

Funnel (where do generations die?):  generated -> schema ok -> rules ok -> bot wins
Lets you answer: "does the few-shot example help?" "is temp 0.8 too high?" with NUMBERS, not vibes.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from game import ContentDB, Level, validate_json, validate_level  # noqa: E402
from game.autoplay import play  # noqa: E402
from lib import get_llm  # noqa: E402

spec = importlib.util.spec_from_file_location("forge", ROOT / "modules/07_loop_engineering/level_forge.py")
forge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(forge)

BRIEFS = ["tiny rat warren", "flooded ossuary with locked door", "skeleton barracks", "wraith chapel", "narrow crypt maze"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--variant", choices=["example", "no_example"], default="example")
    ap.add_argument("--temp", type=float, default=0.8)
    args = ap.parse_args()
    db, llm = ContentDB(), get_llm()
    system = forge.GEN_SYSTEM if args.variant == "example" else forge.GEN_SYSTEM.split("Tiny valid example:")[0]
    funnel = {"generated": 0, "schema_ok": 0, "rules_ok": 0, "bot_wins": 0}
    errors: dict[str, int] = {}
    for i in range(args.n):
        brief = BRIEFS[i % len(BRIEFS)]
        r = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": f"Brief: {brief}"}],
                     schema=Level.model_json_schema(), temperature=args.temp)
        funnel["generated"] += 1
        lv, errs = validate_json(Level, r.text)
        stage = "schema"
        if lv:
            funnel["schema_ok"] += 1
            rep = validate_level(lv, db)
            errs, stage = rep.errors, "rules"
            if rep.ok:
                funnel["rules_ok"] += 1
                if play(lv, db)["won"]:
                    funnel["bot_wins"] += 1
                    stage = "ok"
                else:
                    stage, errs = "bot", ["bot lost/stuck"]
        for e in errs:                               # bucket error types -> tells you WHAT to fix in prompt
            key = stage + ": " + e.split(":")[0].split("(")[0][:50]
            errors[key] = errors.get(key, 0) + 1
        print(f"  #{i + 1:<3} {brief:<34} -> {stage}")
    print(f"\nvariant={args.variant} temp={args.temp}  model={llm.model}")
    for k, v in funnel.items():
        print(f"  {k:<10} {v:>3}/{args.n}  {'█' * int(20 * v / args.n)}")
    print("\ntop failure buckets:")
    for k, v in sorted(errors.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {v:>3}  {k}")
    (ROOT / "runs" / f"eval-levelgen-{args.variant}.json").write_text(json.dumps({"funnel": funnel, "errors": errors}))


if __name__ == "__main__":
    main()
