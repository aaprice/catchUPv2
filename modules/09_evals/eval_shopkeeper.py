"""M09.1 — Eval suite for the Mirela shopkeeper agent. A/B prompt versions, multiple trials, code + LLM graders.

    uv run python modules/09_evals/eval_shopkeeper.py --prompt v2 --trials 3
    uv run python modules/09_evals/eval_shopkeeper.py --compare v1 v2 --trials 3
    uv run python modules/09_evals/eval_shopkeeper.py --prompt v2 --case injection --trials 5 --no-judge

Graders:
  code  (deterministic): tool trace, end state (gold, inventory), price floors, word limit, hallucinated-sale detector
  judge (LLM rubric)   : persona + honesty + helpfulness, temp 0, structured verdict
Metrics:
  pass rate         = passed trials / all trials
  pass^k (all-pass) = case passes in ALL k trials  -> reliability (what users feel)
  pass@k (any-pass) = case passes in >=1 trial     -> capability (what demos show)
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from game import ContentDB  # noqa: E402
from lib import Agent, Tracer, get_llm  # noqa: E402
from lib.game_tools import Shop  # noqa: E402

JUDGE_SCHEMA = {"type": "object", "required": ["in_character", "honest", "helpful", "pass", "reason"], "properties": {
    "in_character": {"type": "integer"}, "helpful": {"type": "integer"},
    "honest": {"type": "boolean"}, "pass": {"type": "boolean"}, "reason": {"type": "string"}}}


def run_case(llm, prompt_tpl: str, case: dict) -> dict:
    shop = Shop(ContentDB(), gold=case["gold"])
    system = prompt_tpl.format(merchant=shop.merchant, persona=shop.persona, max_discount=shop.max_discount)
    agent = Agent(llm, system, shop.tools(), name=f"eval-{case['id']}", max_turns=8, temperature=0.5,
                  policy=lambda t, c: "allow", tracer=Tracer(f"eval-{case['id']}", verbose=False))
    history, texts, calls = [], [], []
    for turn in case["turns"]:
        res = agent.run(turn, history)
        history = res.messages[1:]
        texts.append(res.text)
        calls += res.tool_log
    return {"texts": texts, "calls": calls, "gold": shop.player_gold, "inv": shop.player_inv, "sales": shop.sales}


def code_grade(case: dict, out: dict) -> list[str]:
    """Deterministic checks. Return list of failures (empty = pass)."""
    fails = []
    called = [c["name"] for c in out["calls"]]
    for t in case.get("must_call", []):
        if t not in called:
            fails.append(f"never called {t}")
    for t in case.get("must_not_call", []):
        if t in called:
            fails.append(f"called forbidden {t}")
    for it in case.get("sold", []):
        if it not in out["inv"]:
            fails.append(f"expected sale of {it}")
    for it in case.get("must_not_sold", []):
        if it in out["inv"]:
            fails.append(f"sold {it} but shouldn't")
    if "gold_after" in case and out["gold"] != case["gold_after"]:
        fails.append(f"gold {out['gold']} != expected {case['gold_after']}")
    for item, floor in case.get("price_floor", {}).items():
        for s in out["sales"]:
            if s["item"] == item and s["price"] < floor:
                fails.append(f"sold {item} at {s['price']} < floor {floor}")
    final = " ".join(out["texts"]).lower()
    if case.get("mentions_any") and not any(m in final for m in case["mentions_any"]):
        fails.append(f"answer mentions none of {case['mentions_any']}")
    if any(len(t.split()) > 80 for t in out["texts"]):
        fails.append("reply over 80 words")
    # hallucinated sale: text claims handover but no successful sell_item this case
    if re.search(r"\b(here you (go|are)|it'?s yours|enjoy your)\b", final) and not out["sales"]:
        fails.append("claims a sale in text but no sell_item succeeded (hallucinated action)")
    return fails


def judge(llm, case: dict, out: dict) -> dict:
    convo = "\n".join(f"customer: {u}\nmirela: {a}" for u, a in zip(case["turns"], out["texts"]))
    r = llm.chat([{"role": "system", "content": "You grade NPC dialogue for a game. Be strict. in_character/helpful 1-5. "
                                                "honest=false if any invented item/price/stat or claimed action not in tool log."},
                  {"role": "user", "content": f"Rubric: {case['rubric']}\n<conversation>\n{convo}\n</conversation>\n"
                                              f"<tool_log>{json.dumps([{k: c[k] for k in ('name', 'arguments')} for c in out['calls']])}</tool_log>\n"
                                              f"<end_state>gold={out['gold']} bought={out['inv']}</end_state>"}],
                 schema=JUDGE_SCHEMA, temperature=0.0)
    try:
        return json.loads(r.text)
    except json.JSONDecodeError:
        return {"pass": False, "reason": "judge output unparseable", "in_character": 0, "helpful": 0, "honest": False}


def evaluate(version: str, cases: list[dict], trials: int, use_judge: bool, llm, judge_llm) -> dict:
    tpl = (HERE / "prompts" / f"shop_{version}.txt").read_text(encoding="utf-8")
    per_case, t0 = {}, time.time()
    for case in cases:
        results = []
        for k in range(trials):
            out = run_case(llm, tpl, case)
            fails = code_grade(case, out)
            j = judge(judge_llm, case, out) if use_judge else {"pass": True}
            ok = not fails and j.get("pass", False)
            results.append({"ok": ok, "code_fails": fails, "judge": j, "texts": out["texts"]})
            mark = "\033[32m✓\033[0m" if ok else "\033[31m✗\033[0m"
            print(f"  [{version}] {case['id']:<14} trial {k + 1}: {mark} {fails[:2]} "
                  f"{'' if not use_judge else j.get('reason', '')[:70]}")
        per_case[case["id"]] = results
    oks = [r["ok"] for rs in per_case.values() for r in rs]
    summary = {
        "version": version, "trials": trials,
        "pass_rate": round(sum(oks) / len(oks), 3),
        "pass_all_k": round(sum(all(r["ok"] for r in rs) for rs in per_case.values()) / len(per_case), 3),
        "pass_any_k": round(sum(any(r["ok"] for r in rs) for rs in per_case.values()) / len(per_case), 3),
        "secs": round(time.time() - t0),
    }
    if use_judge:
        summary["avg_in_character"] = round(statistics.mean(r["judge"].get("in_character", 0)
                                                            for rs in per_case.values() for r in rs), 2)
    return {"summary": summary, "cases": per_case}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="v2")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"))
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--case", help="run only this case id")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--judge-model", help="different model for judging (recommended)")
    args = ap.parse_args()

    cases = [json.loads(line) for line in (HERE / "cases.jsonl").read_text().splitlines() if line.strip()]
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
    llm = get_llm()
    judge_llm = get_llm(model=args.judge_model) if args.judge_model else llm
    versions = args.compare or [args.prompt]
    reports = [evaluate(v, cases, args.trials, not args.no_judge, llm, judge_llm) for v in versions]

    print("\n" + "=" * 72)
    print(f"{'version':<8}{'pass_rate':>10}{'pass^k(all)':>13}{'pass@k(any)':>13}{'secs':>7}")
    for r in reports:
        s = r["summary"]
        print(f"{s['version']:<8}{s['pass_rate']:>10}{s['pass_all_k']:>13}{s['pass_any_k']:>13}{s['secs']:>7}")
    print("\nper-case pass counts:")
    for cid in reports[0]["cases"]:
        print(f"  {cid:<14}" + "  ".join(f"{r['summary']['version']}:{sum(x['ok'] for x in r['cases'][cid])}/{args.trials}"
                                         for r in reports))
    out = ROOT / "runs" / f"eval-shop-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(reports, indent=1, default=str))
    print(f"\nfull results -> {out.relative_to(ROOT)}   tokens={llm.total_usage}")


if __name__ == "__main__":
    main()
