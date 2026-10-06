---
description: Analyze combat balance from live simulation data and propose minimal tweaks
---

## Live balance data
!`uv run python -m game.balance --json`

## Bot playtest of level_01
!`uv run python -m game.autoplay --level level_01`

Task: table per enemy (best/worst hp_lost, survivable?), flag unbeatable/trivial, propose <=3 numeric tweaks
(field, old -> new, why) using damage = max(1, atk - def), player swings first. Do NOT edit files unless told "apply".
