---
name: balance-check
description: Analyze Ember Crypt combat balance from the live fight-simulation report and propose minimal stat tweaks. Use when asked about balance, difficulty, or whether enemies/items are too strong or weak.
allowed-tools: Read Bash(uv run python -m game.*)
---

## Live balance data (injected before you read this)
!`uv run python -m game.balance --json`

## Bot playtest of level_01
!`uv run python -m game.autoplay --level level_01`

## Task
1. Table: per enemy, best-case and worst-case hp_lost, survivable?
2. Flag: unbeatable, trivial (hp_lost 0 with starter gear), or gear that makes everything trivial.
3. Propose at most 3 numeric tweaks (field, old -> new, why). Show expected effect using damage formula
   `max(1, atk - def)`, player swings first.
4. Do NOT edit files unless user says "apply".
