# M08 — Multi-agent systems

> **[v2]** `studio_opencode.py` = studio_claude.py on OpenCode + any model. No `--json-schema` in `opencode run` → orchestrator extracts + validates JSON itself (lesson: harness features become your code). DGX vLLM makes `studio_local.py` fan-out truly parallel.

Goal: know *when* multiple agents help, which topology to pick, and how to wire them (local, Claude Code native, headless fan-out, SDK).

## Analogy: indie game studio

Solo dev (single agent) holds whole game in head → fine for game jam, drowns on bigger project.
Studio: **director** splits work → **designers** work in parallel in own rooms (own context) → **QA** who didn't build it tests it → director integrates.
Benefits only real if: tasks separable, each needs lots of private scratch work, independent review matters.
Costs: meetings (coordination tokens), miscommunication (lossy handoffs), payroll (N× tokens).

## When multi-agent wins / loses

| Wins | Loses |
|---|---|
| Breadth: many independent subtasks (research N topics, design N enemies) | Tightly coupled work (one function, one level map) |
| Context isolation: subtask generates junk (logs, file dumps) parent shouldn't see | Small tasks: coordination overhead > work |
| Independent verification (maker ≠ checker) | Shared mutable state w/o clear ownership |
| Parallel wall-clock speed | Tight token budget (multi-agent ≈ several× tokens) |
| Specialization: different tools/model/prompt per role | When single agent + better tools would do |

Rule: start single agent. Split when you can name the **context** problem or **parallelism** win.

## Topologies

```
 ORCHESTRATOR-WORKERS          PIPELINE                      MAKER-CHECKER
   orch                        A ──► B ──► C                  maker ──► checker ──┐
  / | \                        (stage outputs feed next)        ▲                 │ fail+issues
 w1 w2 w3 → merge                                               └─────────────────┘

 FAN-OUT/FAN-IN (map-reduce)   DEBATE / JURY                  HIERARCHICAL
 split → N parallel → reduce   N agents argue → judge picks   orch → sub-orch → workers (depth limit!)
```
`studio_local.py` combines: orchestrator plans → fan-out designers → pipeline stage (lore) → maker-checker QA w/ repair round.

## Communication: how agents hand off

| Method | Example | Pros/cons |
|---|---|---|
| **Submit tool** (structured) | `submit_enemy(json)` writes blackboard | validated at handoff; best default |
| **Structured output** | `claude -p --json-schema` → `.structured_output` | schema-enforced, process-isolated |
| **Blackboard / files** | `board` dict; git repo; `game/data/generated/` | simple, inspectable; need ownership rules |
| Free text summary | subagent final message | lossy; parse fragility; fine for humans |

**Handoffs are where multi-agent systems break.** Telephone game. Make handoff payloads small, typed, validated.

## Four ways to run multi-agent here

| Way | File | Engine | Notes |
|---|---|---|---|
| Your harness, threads | `studio_local.py` | Ollama | full control; see every message; free |
| Claude Code subagents (interactive) | `.claude/agents/*.md` | Pro | Claude decides delegation; best UX |
| Headless fan-out | `studio_claude.py` | Pro (`claude -p` ×N) | your code orchestrates; deterministic topology |
| Agent SDK | `sdk_demo.py` | API key (officially) | library form of Claude Code; in-process tools |

Claude Code also has: **agent teams** (coordinated multi-session teams, experimental), **worktree isolation** (`isolation: worktree` in subagent → each worker edits separate git worktree; no file conflicts), background agents (Ctrl+B), nested subagents (default depth limit 3).

## Run

```powershell
# local (set OLLAMA_NUM_PARALLEL=3 + restart Ollama for real parallelism)
uv run python modules/08_multi_agent/studio_local.py --pitch "frost-bitten crypt wing"
uv run python modules/08_multi_agent/studio_local.py --pitch "frost-bitten crypt wing" --sequential   # compare time

# Claude headless fan-out (Pro usage!)
uv run python modules/08_multi_agent/studio_claude.py --workers 3 --model haiku

# Claude Code interactive subagents
claude
> Use the level-designer subagent to make "spore_cellar" (14x9, fungal theme, 2 enemies),
  then the qa-verifier subagent to check it independently. Report both outputs.
```
Watch in interactive mode: main context stays small — designer's 15 tool calls never enter your window. `/context` before/after.

## Design rules (pin these)

1. **One owner per artifact.** Two agents editing same file = merge hell. Use worktrees or partition outputs.
2. **Checker never sees maker's reasoning**, only artifact + spec. Otherwise it inherits maker's blind spots.
3. **Cheap models for breadth, strong model for judgment.** haiku workers, sonnet checker.
4. **Bound everything**: max workers, max turns per worker, max repair rounds.
5. **Trace per agent** (`runs/*-<role>.jsonl`). Debugging multi-agent without per-agent traces = impossible.
6. **Orchestrator plan = structured data**, not prose. Code dispatches it.

## Exercises

- ★ Time `studio_local.py` parallel vs `--sequential` with `OLLAMA_NUM_PARALLEL` 1 vs 3. Explain result (hint: GPU batching vs queueing).
- ★ Add `--workers` to studio_claude.py using sonnet vs haiku; compare quality vs usage.
- ★★ **Debate pattern**: 2 critic agents (one "too hard", one "too easy" bias) argue about a forged level (M07), judge agent decides changes.
- ★★ Make checker in `studio_local.py` use a *different* model (`get_llm(model=...)`). Does PASS rate drop? (= less self-agreement.)
- ★★★ **Playtester swarm**: N agents play same level via `lib.game_tools.playtest_tools` with different personas ("cautious", "speedrunner", "looter"); aggregate win rates + where each died → heatmap of danger cells (ASCII). Agent-based playtesting = real industry use.
- ★★★ Worktree-isolated parallel Ralph: 2 Claude workers each implementing a different FEATURES.md item in separate worktrees (`git worktree add`), then merge. Observe conflicts.

Next: [M09 Evals](../09_evals/).
