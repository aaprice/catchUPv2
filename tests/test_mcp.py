"""MCP server tested in-process through real MCP client (no subprocess, no model)."""
import importlib.util
import json
from pathlib import Path

from lib.mcp_bridge import MCPBridge

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ember_mcp", ROOT / "modules/05_mcp/ember_mcp_server.py")
ember = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ember)


def test_mcp_tools_resources_prompts():
    b = MCPBridge(ember.mcp)
    try:
        tools = {t.name: t for t in b.tools()}
        assert {"list_content", "simulate_fight", "validate_level_json", "save_level"} <= set(tools)
        r = json.loads(tools["simulate_fight"](enemy_id="crypt_rat"))
        assert r["player_survives"] is True
        lvl = (ROOT / "game/data/level_01.json").read_text()
        assert tools["validate_level_json"](level_json=lvl).startswith("VALID: True")
        assert "REFUSED" in tools["save_level"](name="bad", level_json='{"name":"x"}')
        assert "gravewarden" in b.read_resource("ember://enemies")
        assert "Gravewarden" in b.read_resource("ember://lore/03_gravewarden")
        assert "propose_entity" in b.get_prompt("design_enemy", {"theme": "ice"})
    finally:
        b.close()
