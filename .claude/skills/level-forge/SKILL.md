---
name: level-forge
description: Generate, validate, playtest and save a new Ember Crypt level from a short brief, iterating until it passes all checks. Use when asked to make/generate/design a level.
argument-hint: "<brief, e.g. 'flooded crypt, 16x10, 3 enemies, door + key'> [save_name]"
---

Brief: $ARGUMENTS

This is a **generate -> verify -> fix loop** (M07) run by you inside Claude Code.

Loop (max 5 iterations; report iteration count):
1. Draft level JSON per brief (read `.claude/skills/ember-content/reference.md` for rules).
2. `mcp__ember__validate_level_json` (OpenCode: `ember_validate_level_json`). If errors -> fix exactly those, go to 2.
3. Save with `mcp__ember__save_level` (OpenCode: `ember_save_level`) (name from args or snake_case of theme).
4. `uv run python -m game.autoplay --level <name>`. If not won -> diagnose (too hard? stuck?), adjust, go to 2.
5. Delegate independent review to the `qa-verifier` subagent with the level name. If FAIL -> address findings, go to 2.
6. Final: ASCII map, stats, autoplay result, QA verdict.
