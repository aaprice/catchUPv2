# M07 — Loop engineering

> **[v2]** OpenCode/any-model Ralph: `pwsh modules/07_loop_engineering/ralph/ralph_opencode.ps1 -Model ollama/qwen3.5:9b` (permissions in `.opencode/agents/ralph.md`). `level_forge.py` runs on any `LLM_PROFILE`.

Goal: stop prompting step by step. Design loops that run agents against **verifiable goals** until done.

> "I don't prompt Claude anymore. I write loops and the loops do the work." — Boris Cherny (Claude Code lead), 2026.
> Term formalized mid-2026 (Addy Osmani) building on "harness engineering".

## Analogy

Blacksmith forging blade: **heat → hammer → quench → inspect → repeat** until blade passes test. Smith doesn't swing once and hope.
- Hammer = generator (LLM).
- Inspection = verifier (tests, validator, bot, critic).
- Smith's eye on *specific* flaw = feedback.
- "Good enough or out of charcoal" = stop condition.

Game-dev mapping: you already do this — **playtest loop**. Build → playtest → notes → fix. Loop engineering = automating that loop with agents on both sides.

## Inner loop vs outer loop

```
 OUTER LOOP (you engineer this)                          INNER LOOP (harness, M03)
 ┌──────────────────────────────────────────┐           ┌────────────────────────────┐
 │ spec/goal ─► run agent ─► artifact        │           │ llm → tool → result → llm  │
 │     ▲                       │             │  each     │  ...until model stops      │
 │     │                  VERIFIERS          │  "run" =  └────────────────────────────┘
 │  feedback ◄── fail ──  (code→bot→critic)  │  one inner loop
 │                          │ pass           │
 │                    STOP: done │ budget │ no-progress │ max iters │ human gate
 └──────────────────────────────────────────┘
```

## Loop anatomy checklist (every loop needs all 6)

| Part | Question | Level Forge | Ralph |
|---|---|---|---|
| **Goal/spec** | what is "done", in checkable terms? | brief + all verifiers pass | all FEATURES.md boxes ticked |
| **Actor** | who produces artifact? | local LLM w/ Level schema | Claude Code `-p` |
| **Verifier** | how checked, cheapest first? | schema → rules → bot → critic | pytest (+ stop-hook) |
| **Feedback** | what goes back, how specific? | exact errors from first failing stage | test failures in agent's own run |
| **State/memory** | what persists between iterations? | last attempt + feedback (fresh) or history | git commits + FEATURES.md + NOTES.md |
| **Stop** | when quit? | pass / max iters / token budget / no-progress → temp bump | backlog empty / RALPH_DONE / red tests / max iters |

Missing verifier → loop optimizes nothing. Missing stop → loop burns money. Vague feedback → loop oscillates.

## Patterns

1. **Validate–retry** (M02): schema + errors back. Smallest loop.
2. **Generator–verifier** (`level_forge.py --no-critic`): deterministic checks. Best ROI; build these first.
3. **Evaluator–optimizer** (`level_forge.py`): LLM critic w/ rubric for taste. Use *after* deterministic gates. Critic temp 0, different prompt, ideally **different model** (`--critic-model`) → less self-grading bias.
4. **Ralph loop** (`ralph/`): `while true: cat PROMPT.md | agent`. Each iteration **fresh context**, state in files+git, tests = back-pressure. Named after Ralph Wiggum (Geoffrey Huntley): dumb persistence + good guardrails beats clever single shot.
5. **Stop-hook gate** (M06 `stop_gate.py`): loop *inside* one Claude Code session — Claude can't stop until tests green.
6. **Scheduled/automated loops**: `/loop` in Claude Code, cron/CI, scheduled tasks → triage, nightly content gen, dependency bumps. Loop engineering's "automations" block.
7. **Maker–checker w/ subagents** (M08): verifier is separate agent with own context.

Osmani's six building blocks map onto this course: automations (6) · worktrees (M08 isolation) · skills (M06) · connectors/MCP (M05) · sub-agents (M06/M08) · memory (M04, NOTES.md).

## Context strategy: fresh vs accumulate

```
 accumulate: [sys, try1, fb1, try2, fb2, try3, fb3 ...]   remembers everything; context rot; tokens grow ~N²
 fresh:      [sys, brief, LAST try, LAST feedback]          constant size; may repeat old mistakes → fix w/ NOTES file
```
Ralph = fresh + NOTES.md (agent writes own learnings). Best of both: bounded context, durable lessons.

## Failure modes (you WILL hit these)

| Failure | Looks like | Guard |
|---|---|---|
| **Reward hacking** | agent edits tests / validator to pass | disallow edits to tests (`--disallowedTools "Edit(tests/...)"`), CI re-runs originals, review diffs |
| **Oscillation** | fix A breaks B, fix B breaks A | feedback includes ALL errors; keep best-so-far (forge does) |
| **No progress** | same error 3× | detector → change temperature / strategy / escalate to human |
| **Critic gaming** | output flatters rubric, not fun | deterministic gates first; rotate critic; human spot-check |
| **Runaway cost** | 50 iterations overnight | max iters + token budget + `--max-turns` per run |
| **Silent drift** | each step valid, whole thing wrong | periodic human checkpoints; eval suite (M09) on outputs |

## Run

```powershell
# Level Forge (local, free)
uv run python modules/07_loop_engineering/level_forge.py --no-critic --brief "tiny rat warren" --name warren
uv run python modules/07_loop_engineering/level_forge.py --brief "flooded ossuary with locked door" --name flooded
uv run python modules/07_loop_engineering/level_forge.py --context accumulate --brief "flooded ossuary" --name flooded2
uv run python -m game.play --level flooded
```
Watch `[forge] loop: iter N ... stage=` lines. Which stage blocks most? (Usually `rules` on small models → map geometry is hard for LLMs.)

```powershell
# Ralph (Claude Code, uses Pro quota; ~1 feature per iteration)
git add -A; git commit -m "pre-ralph"                       # clean tree first
pwsh modules/07_loop_engineering/ralph/ralph.ps1 -MaxIters 2 -Model sonnet
git log --oneline ralph; git diff main..ralph                # REVIEW what it did
git switch main                                              # merge if happy: git merge ralph
```
Free variant: run Ralph against local model (M06 §8 env vars) with `-Model qwen3:8b`. Expect more red stops — that's the guardrails working.

## Exercises

- ★ Forge: add verifier V2.5 "≥ 1 potion reachable before first enemy with threat ≥ 13". Measure iterations-to-pass before/after.
- ★ Run forge 5× each with `--context fresh` vs `accumulate`. Compare pass rate, iterations, tokens. Write 3-line conclusion.
- ★★ **Hybrid generation**: LLM outputs *room graph* (`rooms:[{w,h,theme}], links:[[a,b,"door"|"open"]]`); Python lays out geometry. LLM = intent, code = geometry. Pass rate?
- ★★ Add `FEATURES.md` item of your own (e.g. "ranged enemy") with crisp acceptance criteria. Run 1 Ralph iteration. Was spec clear enough? Spec quality = loop quality.
- ★★★ Build **mini-Ralph locally**: `lib.Agent` + tools `read_file`, `write_file`, `run_tests` (restricted to `game/` + `tests/test_features.py`) + outer loop in Python. Local model as coding agent. You just built a tiny Claude Code.
- ★★★ Visual loop: Claude Code + Blender MCP: "build level, render, look at PNG, critique readability, adjust props; stop when you'd ship it or 4 renders". Multimodal verifier.

Next: [M08 Multi-agent](../08_multi_agent/).
