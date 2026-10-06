# catchUPv2 — AI Engineering Dojo (Ember Crypt edition, model-agnostic)

Senior dev, weak on AI tooling → fix that. Learn by building around tiny roguelike **Ember Crypt**.
Not shipping game. Game = testbed: deterministic world agents can poke, validate, play, extend.

Style note: docs written terse ("caveman"). Technical content complete; filler cut.

## What's new in v2 (v1 kept untouched in `../CatchUP`)

| Change | Where |
|---|---|
| **Runs on any model**: Gemma 4, Qwen, gpt-oss via Ollama / llama.cpp / **DGX vLLM**. One line in `.env`: `LLM_PROFILE=gemma4-26b` | `lib/profiles.py`, [M11](modules/11_open_models/) |
| **Prompt-mode tool calling**: harness does tool calling itself when a model's native tool calls are flaky | `lib/llm.py`, M11 |
| **Model bake-off**: pick engine by measured tool/JSON/speed scores on your hardware | `modules/11_open_models/bakeoff.py` |
| **OpenCode harness track** (open source, any model, work-friendly) next to Claude Code | [M06b](modules/06b_opencode/), `opencode.json`, `.opencode/`, `AGENTS.md` |
| OpenCode versions of Ralph loop + headless fan-out | `ralph_opencode.ps1`, `studio_opencode.py` |
| **Unity replaces UE5**: MCP bridge + playable grey-box + Ollama NPC in-engine | [modules/05_mcp/unity](modules/05_mcp/unity/) |
| **Godot** headless importer (recommended agent-friendly engine) | `modules/10_capstone/godot/` |

Every `[v2]` tag in code/docs marks something changed or added. Full list: [V2_CHANGES.md](V2_CHANGES.md).

## Two tracks

| | Home track | Work track (no Claude) |
|---|---|---|
| Engine | Ollama (any) / Claude | Ollama Gemma/gpt-oss, llama.cpp, **DGX vLLM** |
| Harness module | M06 Claude Code | **M06b OpenCode** |
| Order | M00→M10 | M00→M03 → **M11** → M04 → M05 → **M06b** → M07→M10 |

---

## Big picture — one diagram whole course hangs on

```
                         ┌──────────────────────────── YOU (goals, taste, review) ───────────────────────────┐
                         │                                                                                   │
 M10 Capstone            │   pipeline: generate content → forge level → eval gate → play → Blender/Unity/Godot│
 M09 Evals               │   "unit tests for probabilistic code": datasets, graders, LLM-judge, pass rates    │
 M08 Multi-agent         │   orchestrator ─┬─ worker A  ─┐                                                    │
                         │                 ├─ worker B  ─┼─► verifier ─► merge                               │
                         │                 └─ worker C  ─┘   (fan-out, maker/checker, pipelines)             │
 M07 Loop engineering    │   outer loops: generate → VERIFY → feedback → retry until stop condition          │
 M06/06b Agent harness   │   Claude Code or OpenCode: rules · skills · hooks · subagents · headless          │
 M05 MCP                 │   standard plug: any harness ⇄ any tool server (game DB, Blender, Unity)          │
 M04 Context engineering │   what goes in window: compaction · memory files · RAG · caching                  │
 M03 Tools + harness     │   THE AGENT LOOP: llm → tool calls → run → results → llm ... (you write it)       │
 M02 Structured output   │   JSON-schema-constrained output + validation + retry                             │
 M01 Raw API             │   HTTP POST messages[] → text. Stateless. Tokens. Sampling.                       │
 M00 Mental model        │   LLM = next-token function f(context) → token                                    │
 M11 Open models [v2]    │   engines: Gemma/Qwen/gpt-oss · Ollama/llama.cpp/vLLM · tool modes · bake-off     │
                         └───────────────────────────────────────────────────────────────────────────────────┘
```

**Core analogy (carry through every module):**

| Car part | AI part | Where you learn it |
|---|---|---|
| Engine | Model (Gemma 4, Qwen, gpt-oss, Claude, Gemini...) | M00–M01, M11 |
| Fuel line spec | Structured output / JSON schema | M02 |
| Hands & pedals | Tools (function calling) | M03 |
| Chassis + driver loop | **Harness** (agent loop, permissions, hooks) | M03, M06 |
| Glovebox / map | Context: memory, RAG, compaction | M04 |
| Standard OBD-II port | **MCP** — any tool plugs into any car | M05 |
| Cruise control to destination | **Loops** with verifier + stop condition | M07 |
| Convoy / pit crew | **Multi-agent** | M08 |
| Dyno + crash tests | **Evals** | M09 |

Model = commodity engine, swappable. **Harness = where engineering lives.** That's the 2026 shift:
"prompt engineering" → "context engineering" → "harness engineering" → "loop engineering".

---

## Route

| # | Module | Concepts | You build | Backend | Time |
|---|---|---|---|---|---|
| 00 | [Mental model](modules/00_mental_model/) | tokens, context window, statelessness, sampling | nothing; read + diagrams | — | 30m |
| 01 | [Raw API](modules/01_raw_api/) | HTTP wire format, roles, history, temperature | raw HTTP chat; memory demo | Ollama | 1h |
| 02 | [Structured output](modules/02_structured_output/) | JSON schema, constrained decoding, validate→retry | item generator | Ollama | 1h |
| 03 | [Tools + harness](modules/03_tool_use_and_harness/) | function calling, agent loop, permissions, hooks | hand-rolled loop; NPC shopkeeper agent | Ollama | 2–3h |
| 04 | [Context engineering](modules/04_context_engineering/) | budget, compaction, memory files, RAG, prompt caching | lore RAG, memory agent | Ollama | 2h |
| 05 | [MCP](modules/05_mcp/) | servers, tools/resources/prompts, transports, clients | Ember MCP server; Blender bridge | Ollama + Claude Code | 2–3h |
| 06 | [Claude Code as harness](modules/06_claude_code/) | CLAUDE.md, skills, hooks, subagents, plugins, headless | `.claude/` config for this repo | Claude Code (Pro) | 2–3h |
| 06b | [OpenCode as harness](modules/06b_opencode/) **[v2]** | same concepts, any model: AGENTS.md, agents, commands, plugins | `.opencode/` + `opencode.json` | OpenCode + Ollama/DGX | 2–3h |
| 07 | [Loop engineering](modules/07_loop_engineering/) | gen→verify, evaluator-optimizer, Ralph loop, stop hooks | level forge loop; Ralph feature loop | both | 2–3h |
| 08 | [Multi-agent](modules/08_multi_agent/) | orchestrator-workers, fan-out, maker-checker, isolation | game "studio" (local + Claude) | both | 3h |
| 09 | [Evals](modules/09_evals/) | datasets, code graders, LLM judge, pass@k, A/B prompts | shopkeeper + levelgen evals | Ollama | 2h |
| 10 | [Capstone](modules/10_capstone/) | put together | 1-level game built by agent pipeline → Blender / Unity / Godot | all | open |
| 11 | [Open models](modules/11_open_models/) **[v2]** | families, serving, quantization, native vs prompt tools, licenses | profiles, bake-off, DGX serving | Ollama / llama.cpp / vLLM | 2h |

Track progress in [PROGRESS.md](PROGRESS.md). Terms in [GLOSSARY.md](GLOSSARY.md). Quick refs: [Claude Code](docs/claude-code-cheatsheet.md) · [OpenCode](docs/opencode-cheatsheet.md).

---

## How to study each module

1. Read module `README.md` (concept → analogy → diagram → code walkthrough).
2. Run code. **Read the traces** in `runs/` (JSONL) — traces are your debugger now.
3. Do exercises (each has ★ easy / ★★ medium / ★★★ stretch).
4. Tick box in `PROGRESS.md`.
5. Optional tutor: open repo in OpenCode or Claude Code, run `/tutor 03` → agent quizzes you, reviews your exercise code. (Same skill file serves both harnesses.)

## Backends — what costs what

| Backend | Cost | Used for |
|---|---|---|
| **Ollama local** (`LLM_PROFILE=qwen3-8b` / `gemma4-*` / `gpt-oss-20b`) | free | all Python modules; OpenCode at desk |
| **llama.cpp server** (`llamacpp`) | free | most reliable Gemma 4 tool calls (`--jinja`); offline GGUF |
| **DGX vLLM** (`dgx-vllm`) | free (your hardware) | big models, many parallel agents (M08), shared team endpoint |
| Gemini API free tier (`gemini`) | free, rate-limited | home only / if policy allows |
| Claude Code (Pro) | plan limits | home track M06 |

Small local models fail more. **That's a feature for learning**: failures show *why* validators, retries, evals exist. Frontier model hides those lessons.

## Repo layout

```
CatchUP/
├─ README.md  SETUP.md  GLOSSARY.md  PROGRESS.md  CLAUDE.md   ← start here
├─ game/                Ember Crypt core (pure Python, deterministic, tested)
│  ├─ content.py        pydantic schemas = single source of truth
│  ├─ level.py          deterministic level verifier (BFS solvability, budget)
│  ├─ world.py          turn-based sim; Game.step(action)
│  ├─ play.py           terminal play      balance.py   fight math report
│  ├─ autoplay.py       deterministic bot playtester (cheap verifier)
│  └─ data/             items, enemies, level_01, shop, lore/*.md
├─ lib/                 YOUR mini agent framework
│  ├─ llm.py            provider adapters (Ollama native, OpenAI-compatible, Mock) + [v2] prompt-mode tools
│  ├─ profiles.py       [v2] model profiles (gemma4, qwen, gpt-oss, llamacpp, dgx-vllm...)
│  ├─ tools.py          @tool → JSON schema
│  ├─ harness.py        THE agent loop (policy, hooks, stop-veto, compaction)
│  ├─ trace.py          JSONL traces + console
│  └─ game_tools.py     shop + playtest tool sets
├─ modules/00..10/      lessons: README + runnable code + exercises
├─ capstone/            end-to-end pipeline
├─ tools/check_setup.py env check + model recommendation
├─ docs/                cheat sheets
├─ AGENTS.md            [v2] harness-neutral project rules (CLAUDE.md imports it)
├─ opencode.json        [v2] OpenCode: providers (ollama/llamacpp/dgx), MCP, permissions
├─ .opencode/           [v2] OpenCode agents, commands, plugins (M06b)
├─ .claude/             Claude Code config: skills (shared w/ OpenCode), hooks, subagents (M06)
├─ .mcp.json            MCP servers for Claude Code (ember, blender, unity)
├─ tests/               pytest — also back-pressure for agent loops
└─ runs/                traces (gitignored)
```

Next: [SETUP.md](SETUP.md).
