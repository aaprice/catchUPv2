# M09 — Evals

Goal: replace "seems to work" with numbers. Evals = **unit tests for probabilistic code**. Without them, every prompt tweak is a guess and every model swap is a gamble.

## Analogy

Game balance. You don't ship after 1 playthrough. You run telemetry over 1000 sessions: win rate per level, where players die, which items nobody buys. Evals = telemetry + regression tests for your AI features.

## Why normal tests aren't enough

| Unit test | Eval |
|---|---|
| deterministic → 1 run proves it | stochastic → need N trials, report rates |
| exact assertion | graded: code checks + rubric + judge |
| pass/fail | pass rate, pass^k, score distributions, cost, latency |
| catches regressions in code | catches regressions in prompt, model, tools, harness |

## Grader types (cheapest → most expensive)

```
 CODE GRADERS ─────────► LLM JUDGE ─────────► HUMAN REVIEW
 tool trace, end state,   rubric, structured,    spot-check judge,
 regex, schema, sim       temp 0, other model     calibrate rubric
 free, exact              cheap, fuzzy, biased    slow, gold standard
```
Rule: everything checkable by code → code grader. Judge only for taste/tone/honesty nuance. Periodically **check judge vs your own grades** on ~20 samples (judge calibration). Known judge biases: favors longer answers, own model family's style, position (first option) in comparisons.

## Metrics that matter

- **pass rate** over all trials.
- **pass^k** (all k trials pass) = *reliability* — what users experience. Agents: this drops fast (M00 compounding law).
- **pass@k** (any trial passes) = *capability* — "can it ever do this?".
- Gap between pass@k and pass^k = flakiness. Big gap → work on consistency (lower temp, tighter tools, validators), not capability.
- Also track: tokens, latency, tool calls per task.

## Eval-driven development loop

```
 write cases (incl. adversarial) ─► baseline run ─► read FAILING traces ─► change ONE thing (prompt/tool/model)
        ▲                                                                              │
        └─────────────── keep if metric up & no case regressed ◄── re-run ◄────────────┘
```
"Read the failing traces" is the step people skip. Numbers say *that*; traces say *why*.

## Dataset (`cases.jsonl`)

8 cases: happy path, multi-turn memory, can't-afford, lowball haggling, **prompt injection**, advice requiring tool use. Each case = turns + code checks + judge rubric. Grows over time: every bug found in play → new case (regression).

## Run

```powershell
uv run python modules/09_evals/eval_shopkeeper.py --compare v1 v2 --trials 3
uv run python modules/09_evals/eval_shopkeeper.py --prompt v2 --case injection --trials 5 --no-judge
uv run python modules/09_evals/eval_levelgen.py --n 10 --variant example
uv run python modules/09_evals/eval_levelgen.py --n 10 --variant no_example
```
v1 = one-liner persona prompt. v2 = M03 rules prompt. Expect v2 ≫ v1 on `too_poor`, `injection`, `advice`. If not — read traces in `runs/` and find out why.

Model swap test: same suite, `LLM_MODEL=qwen3:4b` vs `qwen3:8b` vs Gemini (`LLM_PROVIDER=openai`). Now "which model?" is a data question.

## Exercises

- ★ Add 3 cases: buying 2 items in one message; asking about item not in stock (`dragon_sword`); rude customer.
- ★ Run judge with different model (`--judge-model`). Agreement rate with default judge?
- ★★ Write `shop_v3.txt` that beats v2 on pass^3 without hurting any case. Commit only if it wins (eval-gated prompt change).
- ★★ Calibrate judge: hand-grade 15 transcripts from `runs/eval-shop-*.json`; compute agreement %. Rewrite rubric where they disagree.
- ★★★ CI gate: `tests/test_evals_smoke.py` (marked slow) runs 3 critical cases × 2 trials; fails if pass rate < 0.8. Wire into Ralph (M07) as additional back-pressure.
- ★★★ Eval the **harness**, not just prompt: toggle hooks / compaction / tool descriptions and measure. That's harness engineering with evidence.

Next: [M10 Capstone](../10_capstone/).
