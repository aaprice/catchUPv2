---
name: ember-content
description: Rules and workflow for creating or editing Ember Crypt game content (items, enemies, levels, lore). Use whenever adding/changing anything in game/data or designing levels/monsters/items.
---

# Ember Crypt content authoring

Schemas live in `game/content.py` (pydantic = source of truth). Detailed field rules + examples: see [reference.md](reference.md) (read it before first content edit in a session).

## Workflow (always)
1. `mcp__ember__list_content` (OpenCode: `ember_list_content`) to see existing ids + stats (no id reuse).
2. Draft JSON.
3. Validate BEFORE saving:
   - item/enemy -> `mcp__ember__propose_entity` (OpenCode: `ember_propose_entity`)
   - level -> `mcp__ember__validate_level_json` (OpenCode: `ember_validate_level_json`)
4. Fix every ERROR. Treat WARN as design smells; fix if cheap.
5. Save: levels via `mcp__ember__save_level` (OpenCode: `ember_save_level`) (writes game/data/generated/). Items/enemies: append to
   `game/data/generated/` files unless user explicitly asks to edit core files.
6. Levels: confirm beatable: `uv run python -m game.autoplay --level <name>` -> `"won": true`.

## Design taste
- Theme words in names/descriptions (crypt, ember, ash, bone, cinder, grave).
- Threat curve rises toward exit. Key guardian near locked door.
- Every enemy beatable with best gear; not trivial with starter gear.
