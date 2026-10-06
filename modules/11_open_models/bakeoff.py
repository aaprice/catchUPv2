"""[v2] M11 — Model bake-off: which open model + tool mode works best ON YOUR HARDWARE for THIS harness?

    uv run python modules/11_open_models/bakeoff.py --profiles qwen3-8b gemma4-e4b
    uv run python modules/11_open_models/bakeoff.py --profiles gemma4-26b --tool-modes native prompt
    uv run python modules/11_open_models/bakeoff.py --profiles dgx-vllm llamacpp --trials 3

Three measurements (all reuse earlier modules — evals compound):
  tools  : M09 shopkeeper cases, code graders only (no judge -> no judge bias in a model comparison)
  json   : M02 item generation with schema + business rules
  speed  : output tokens/sec on a fixed prompt
Leaderboards online measure models in someone else's harness. This measures YOUR harness. Different answer, often.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lib import LLM  # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


shop_eval = _load("shop_eval", "modules/09_evals/eval_shopkeeper.py")
gen_items = _load("gen_items", "modules/02_structured_output/gen_items.py")
CASE_IDS = ["cheapest_heal", "buy_tonic", "too_poor", "injection", "advice"]


def bench(llm: LLM, trials: int, json_n: int) -> dict:
    cases = [json.loads(line) for line in (ROOT / "modules/09_evals/cases.jsonl").read_text().splitlines() if line.strip()]
    cases = [c for c in cases if c["id"] in CASE_IDS]
    tpl = (ROOT / "modules/09_evals/prompts/shop_v2.txt").read_text(encoding="utf-8")
    t0 = time.time()

    # speed first (also a connectivity check)
    r = llm.chat([{"role": "user", "content": "Describe a crypt corridor in exactly 120 words."}], temperature=0.7,
                 max_tokens=300)
    if r.raw.get("eval_duration"):                       # Ollama reports pure generation time (excludes load)
        tps = r.raw.get("eval_count", 0) / (r.raw["eval_duration"] / 1e9)
    else:
        tps = r.usage.get("out", 0) / max(r.latency_ms / 1000, 0.001)

    tool_ok, tool_n, fails = 0, 0, {}
    for case in cases:
        for _ in range(trials):
            out = shop_eval.run_case(llm, tpl, case)
            f = shop_eval.code_grade(case, out)
            tool_n += 1
            tool_ok += not f
            if f:
                fails[case["id"]] = f[0]
    json_ok = sum(1 for _ in range(json_n) if gen_items.attempt(llm, "frozen ossuary", "schema")[0])
    return {"tools": tool_ok / tool_n, "json": json_ok / json_n, "tok_s": round(tps, 1),
            "secs": round(time.time() - t0), "example_fails": fails, "usage": dict(llm.total_usage)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", nargs="+", default=["qwen3-8b", "gemma4-e4b"])
    ap.add_argument("--tool-modes", nargs="+", default=["profile"], help="native prompt | profile (use profile default)")
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--json-n", type=int, default=4)
    a = ap.parse_args()

    rows = []
    for prof in a.profiles:
        for mode in a.tool_modes:
            llm = LLM(profile=prof, tool_mode=None if mode == "profile" else mode)
            label = f"{prof}/{llm.tool_mode}"
            print(f"\n=== {label}  ({llm.model})")
            try:
                res = bench(llm, a.trials, a.json_n)
            except RuntimeError as e:          # server down / model not pulled
                print(f"  SKIP: {e}")
                continue
            res["label"] = label
            rows.append(res)
            print(f"  tools {res['tools']:.0%}  json {res['json']:.0%}  {res['tok_s']} tok/s  {res['secs']}s  "
                  f"fails={res['example_fails']}")

    if not rows:
        sys.exit("nothing ran. Check SETUP / ollama list.")
    fastest = max(r["tok_s"] for r in rows) or 1
    for r in rows:
        r["score"] = round(0.6 * r["tools"] + 0.3 * r["json"] + 0.1 * r["tok_s"] / fastest, 3)
    rows.sort(key=lambda r: -r["score"])
    print("\n" + "=" * 70)
    print(f"{'profile/tool_mode':<28}{'tools':>7}{'json':>7}{'tok/s':>9}{'secs':>7}{'score':>8}")
    for r in rows:
        print(f"{r['label']:<28}{r['tools']:>7.0%}{r['json']:>7.0%}{r['tok_s']:>9.1f}{r['secs']:>7}{r['score']:>8}")
    best = rows[0]["label"].split("/")
    print(f"\nwinner -> .env:  LLM_PROFILE={best[0]}   LLM_TOOL_MODE={best[1]}")
    out = ROOT / "runs" / f"bakeoff-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=1))
    print(f"saved {out.relative_to(ROOT)}  (score = 0.6 tools + 0.3 json + 0.1 relative speed; change weights to taste)")


if __name__ == "__main__":
    main()
