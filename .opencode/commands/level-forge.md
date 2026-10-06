---
description: Generate, validate, playtest and save a level from a brief. Usage /level-forge <brief> <save_name>
agent: level-designer
subtask: true
---

Brief and save name: $ARGUMENTS
Loop max 5 iterations: draft -> ember_validate_level_json -> fix -> ember_save_level -> autoplay -> fix.
Report iteration count, final ASCII map, stats, autoplay result. Then the user can run @qa-verifier on it.
