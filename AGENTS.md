# AGENTS.md — project rules for ANY coding agent ([v2] canonical; read by OpenCode, Codex, Goose...; Claude Code imports it via CLAUDE.md)

> Teaching note (M06/M06b): this file = persistent context. Keep it SHORT, factual, imperative.
> Every line costs tokens every session — and local models have smaller windows. Long material -> skills.

## What this repo is
Learning repo: AI engineering (harness, tools, MCP, loops, multi-agent, evals) using tiny roguelike **Ember Crypt**.
Owner = senior dev learning AI tooling. When asked to explain, be terse ("caveman" style: drop articles/filler, keep all technical detail), use analogies + code + ASCII diagrams.

## Commands
- Tests: `uv run pytest` (must stay green; harness tests use MockLLM, no model needed)
- Play: `uv run python -m game.play --level <name>`
- Bot playtest: `uv run python -m game.autoplay --level <name>`
- Balance: `uv run python -m game.balance --json`
- Local LLM scripts: `uv run python modules/<NN_x>/<script>.py` (engine = `LLM_PROFILE` in .env; see modules/11_open_models)

## Layout
- `game/` pure deterministic sim. `content.py` pydantic schemas = source of truth. `level.py` = validator.
- `lib/` mini agent framework (llm adapters, harness loop, tools, tracing, MCP bridge).
- `modules/NN_*/` lessons. `capstone/` pipeline.
- Harness config: `.opencode/` + `opencode.json` (OpenCode, any model) · `.claude/` + `.mcp.json` (Claude Code). Skills in `.claude/skills/` are read by both.

## Rules
- Game content (`game/data/*.json`) MUST validate. Use the `ember` MCP server tools `validate_level_json` / `propose_entity` (OpenCode name: `ember_validate_level_json`; Claude Code: `mcp__ember__validate_level_json`), or run tests.
- Generated content goes to `game/data/generated/`, never overwrite `level_01.json`, `items.json`, `enemies.json` unless asked.
- Keep `game/` free of I/O and randomness (determinism = testability).
- Windows host: prefer PowerShell-compatible commands in docs; Python for scripts/hooks.
- Don't `git push`. Commit only when asked.
- Small local models: prefer small focused steps; validate after every content change; never claim success without running the check.
