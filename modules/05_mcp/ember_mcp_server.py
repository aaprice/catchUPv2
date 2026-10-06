"""M05.1 — Ember Crypt MCP server. One server, many clients: Claude Code, Gemini CLI, Claude Desktop, YOUR harness.

Run standalone (stdio; normally the CLIENT launches it, you don't):
    uv run python modules/05_mcp/ember_mcp_server.py
Debug in browser UI:
    npx @modelcontextprotocol/inspector uv run python modules/05_mcp/ember_mcp_server.py
HTTP transport (remote/shared server):
    uv run python modules/05_mcp/ember_mcp_server.py --http      # http://127.0.0.1:8000/mcp

MCP primitives shown:
  tools      = model-controlled actions        (validate_level, simulate_fight, save_level, ...)
  resources  = app/user-controlled read-only data, addressed by URI  (ember://items, ember://level/{name})
  prompts    = user-invoked templates           (design_enemy -> shows as slash command in Claude Code)

!! stdio rule: NEVER print() to stdout in a stdio server. stdout IS the JSON-RPC pipe. Log to stderr.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer  # noqa: E402   (MCP SDK v2. v1 name: from mcp.server.fastmcp import FastMCP)

from game import ContentDB, Enemy, Item, Level, validate_json, validate_level  # noqa: E402
from game.balance import flags, report  # noqa: E402
from game.world import simulate_fight as _sim  # noqa: E402

GEN = ROOT / "game" / "data" / "generated"
db = ContentDB(include_generated=True)   # core + agent-generated content

mcp = MCPServer(
    "ember",
    instructions="Ember Crypt game-content server. Use validate_level before save_level. "
                 "All ids are snake_case. Levels use legend: # wall . floor @ start > exit D locked door.",
)


def log(*a) -> None:
    print("[ember-mcp]", *a, file=sys.stderr)


# ------------------------------------------------------------------ tools (model-controlled)
@mcp.tool()
def list_content(kind: str = "all") -> str:
    """List game content ids with key stats. kind: 'items' | 'enemies' | 'levels' | 'all'."""
    out = {}
    if kind in ("items", "all"):
        out["items"] = {i.id: f"{i.kind} pow{i.power} {i.value}g" for i in db.items.values()}
    if kind in ("enemies", "all"):
        out["enemies"] = {e.id: f"hp{e.hp} atk{e.atk} def{e.defense} threat{e.threat}" for e in db.enemies.values()}
    if kind in ("levels", "all"):
        out["levels"] = sorted(p.stem for p in [*ROOT.glob("game/data/level_*.json"), *GEN.glob("*.json")]
                               if not p.stem.startswith(("items_", "enemies_")))
    return json.dumps(out, indent=1)


@mcp.tool()
def get_entity(entity_id: str) -> str:
    """Full JSON of one item or enemy by id."""
    e = db.items.get(entity_id) or db.enemies.get(entity_id)
    return e.model_dump_json(indent=1) if e else f"ERROR: unknown id '{entity_id}'. Use list_content."


@mcp.tool()
def simulate_fight(enemy_id: str, weapon_id: str = "", armor_id: str = "", player_hp: int = 30) -> str:
    """Deterministic duel: base player (atk 4, def 1) + optional gear vs enemy. Returns turns, hp lost, survival."""
    e = db.enemies.get(enemy_id)
    if not e:
        return f"ERROR: unknown enemy '{enemy_id}'"
    w, a = db.items.get(weapon_id), db.items.get(armor_id)
    return json.dumps(_sim(4 + (w.power if w else 0), 1 + (a.power if a else 0), player_hp, e))


@mcp.tool()
def balance_report() -> str:
    """Red flags across all enemy x gear combos (unbeatable enemies, harmless enemies). Empty flags = healthy."""
    return json.dumps({"flags": flags(report(db))})


@mcp.tool()
def validate_level_json(level_json: str) -> str:
    """Validate a level (JSON string matching Level schema). Returns VALID true/false, errors, warnings, stats.
    Checks: rectangular map, border walls, one @ and one >, placements on floor, ids exist, threat budget,
    exit reachable (doors need reachable key)."""
    lv, errs = validate_json(Level, level_json)
    if errs:
        return "VALID: False\n" + "\n".join(f"SCHEMA ERROR: {e}" for e in errs)
    return validate_level(lv, db).as_feedback()


@mcp.tool()
def save_level(name: str, level_json: str) -> str:
    """Validate then save level to game/data/generated/<name>.json. Refuses invalid levels. name: snake_case."""
    if not name.replace("_", "").isalnum():
        return "ERROR: name must be snake_case alphanumeric"
    lv, errs = validate_json(Level, level_json)
    if errs:
        return "REFUSED (schema): " + "; ".join(errs)
    rep = validate_level(lv, db)
    if not rep.ok:
        return "REFUSED (rules):\n" + rep.as_feedback()
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN / f"{name}.json").write_text(lv.model_dump_json(indent=2), encoding="utf-8")
    log("saved level", name)
    return f"SAVED game/data/generated/{name}.json  play: uv run python -m game.play --level {name}"


@mcp.tool()
def propose_entity(kind: str, entity_json: str) -> str:
    """Validate a NEW item or enemy (kind='item'|'enemy') without saving. Returns errors or computed stats."""
    model = {"item": Item, "enemy": Enemy}.get(kind)
    if not model:
        return "ERROR: kind must be 'item' or 'enemy'"
    obj, errs = validate_json(model, entity_json)
    if errs:
        return "INVALID: " + "; ".join(errs)
    if obj.id in db.items or obj.id in db.enemies:
        return f"INVALID: id '{obj.id}' already exists"
    if isinstance(obj, Enemy):
        bad = [loot for loot in obj.loot if loot not in db.items]
        if bad:
            return f"INVALID: loot ids not found {bad}"
        fights = {w: _sim(4 + db.items[w].power, 3, 30, obj)["player_survives"] for w in ("rusty_sword", "ember_blade")}
        return f"OK threat={obj.threat} survivable_with={fights}"
    return "OK"


# ------------------------------------------------------------------ resources (app-controlled data)
@mcp.resource("ember://items", mime_type="application/json")
def items_resource() -> str:
    """All items as JSON."""
    return json.dumps([i.model_dump() for i in db.items.values()], indent=1)


@mcp.resource("ember://enemies", mime_type="application/json")
def enemies_resource() -> str:
    """All enemies as JSON."""
    return json.dumps([e.model_dump() for e in db.enemies.values()], indent=1)


@mcp.resource("ember://level/{name}", mime_type="application/json")
def level_resource(name: str) -> str:
    """A level by name (level_01 or a generated one)."""
    return db.load_level(name).model_dump_json(indent=1)


@mcp.resource("ember://lore/{topic}", mime_type="text/markdown")
def lore_resource(topic: str) -> str:
    """Lore doc by file stem, e.g. 03_gravewarden."""
    p = ROOT / "game/data/lore" / f"{topic}.md"
    return p.read_text(encoding="utf-8") if p.exists() else f"unknown lore topic. options: " + \
        ", ".join(x.stem for x in (ROOT / "game/data/lore").glob("*.md"))


# ------------------------------------------------------------------ prompts (user-invoked templates)
@mcp.prompt()
def design_enemy(theme: str) -> str:
    """Workflow template: design + validate a new enemy for a theme."""
    return (f"Design one new Ember Crypt enemy themed '{theme}'.\n"
            "1. Call list_content to see existing enemies and items.\n"
            "2. Draft enemy JSON (id,name,hp,atk,defense,xp,loot,description).\n"
            "3. Call propose_entity(kind='enemy', ...) and iterate until OK with threat 10-25 and "
            "survivable with ember_blade but NOT trivially with rusty_sword.\n"
            "4. Show final JSON + one-line lore hook.")


if __name__ == "__main__":
    if "--http" in sys.argv:
        log("serving streamable HTTP on http://127.0.0.1:8000/mcp")
        mcp.run("streamable-http")
    else:
        mcp.run()  # stdio
