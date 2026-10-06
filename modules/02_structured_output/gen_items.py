"""M02 — Structured output: 3 escalating strategies to get VALID game items from an LLM.

    uv run python modules/02_structured_output/gen_items.py --mode prompt --n 5
    uv run python modules/02_structured_output/gen_items.py --mode schema --n 5
    uv run python modules/02_structured_output/gen_items.py --mode retry  --n 5 --theme "frozen ossuary"

prompt = ask nicely for JSON in prose            (fragile)
schema = constrained decoding w/ JSON Schema      (syntax guaranteed, semantics not)
retry  = schema + validators + feed errors back   (the pattern you'll use forever)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from game import ContentDB, Item, validate_json  # noqa: E402
from lib import get_llm  # noqa: E402

db = ContentDB()


def business_rules(item: Item) -> list[str]:
    """Semantic checks schema can't express. THIS is where your domain knowledge lives."""
    errs = []
    if item.id in db.items:
        errs.append(f"id '{item.id}' already exists; pick new id")
    if item.kind in ("weapon", "armor") and item.value < item.power * 8:
        errs.append(f"value {item.value} too cheap for power {item.power}; need >= {item.power * 8}")
    if item.kind in ("key", "trinket") and item.power != 0:
        errs.append("keys/trinkets must have power 0")
    if item.kind == "potion" and not 1 <= item.power <= 6:
        errs.append("potion power must be 1..6 (heals power*5)")
    return errs


def build_prompt(theme: str) -> str:
    examples = json.dumps([db.items["ember_blade"].model_dump(), db.items["red_tonic"].model_dump()], indent=1)
    return (f"Design ONE new item for crypt roguelike 'Ember Crypt'. Theme: {theme}.\n"
            f"Existing ids (don't reuse): {sorted(db.items)}\n"
            f"Examples of valid items:\n{examples}\n"
            "Output a single JSON object with keys id,name,kind,power,value,description. No prose.")


def attempt(llm, theme: str, mode: str, max_tries: int = 3) -> tuple[Item | None, int, list[str]]:
    messages = [{"role": "user", "content": build_prompt(theme)}]
    schema = Item.model_json_schema() if mode in ("schema", "retry") else None
    errs: list[str] = []
    for i in range(1, (max_tries if mode == "retry" else 1) + 1):
        reply = llm.chat(messages, schema=schema, temperature=0.9)
        raw = reply.text.strip().removeprefix("```json").removesuffix("```").strip()
        item, errs = validate_json(Item, raw)
        if item:
            errs = business_rules(item)
            if not errs:
                return item, i, []
        if mode != "retry":
            break
        # FEEDBACK LOOP: show model its output + precise errors. Specific errors -> fast convergence.
        messages += [{"role": "assistant", "content": reply.text},
                     {"role": "user", "content": "Invalid. Fix ALL of these and output corrected JSON only:\n- "
                                                 + "\n- ".join(errs)}]
    return None, i, errs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["prompt", "schema", "retry"], default="retry")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--theme", default="cursed relics of the Long Winter")
    ap.add_argument("--save", action="store_true", help="write accepted items to game/data/generated/items_gen.json")
    args = ap.parse_args()

    llm = get_llm()
    print(f"[{llm}] mode={args.mode} n={args.n}\n")
    ok, tries_total, accepted = 0, 0, []
    for k in range(args.n):
        item, tries, errs = attempt(llm, args.theme, args.mode)
        tries_total += tries
        if item:
            ok += 1
            accepted.append(item.model_dump())
            db.items[item.id] = item          # so next item can't reuse id
            print(f"  #{k + 1} OK  (tries={tries}) {item.id:<20} {item.kind:<8} pow={item.power} val={item.value}")
        else:
            print(f"  #{k + 1} FAIL (tries={tries}) {errs[:3]}")
    print(f"\nvalid {ok}/{args.n}  avg tries {tries_total / args.n:.1f}  tokens {llm.total_usage}")
    if args.save and accepted:
        out = ROOT / "game/data/generated/items_gen.json"
        out.write_text(json.dumps(accepted, indent=2))
        print(f"saved -> {out}")


if __name__ == "__main__":
    main()
