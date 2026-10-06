"""M05.2 — YOUR harness (local Ollama model) using the Ember MCP server. Proves MCP = harness-agnostic.

    uv run python modules/05_mcp/mcp_bridge_agent.py
    uv run python modules/05_mcp/mcp_bridge_agent.py "Design a small 12x8 level with one crypt_rat and save it as tiny_tomb"
    uv run python modules/05_mcp/mcp_bridge_agent.py --http   # connect to server started with --http instead

Same server file Claude Code launches via .mcp.json. Zero changes. That's the point.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lib import Agent, get_llm  # noqa: E402
from lib.mcp_bridge import MCPBridge  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
task = args[0] if args else ("Which enemy is most dangerous for a player with rusty_sword and bone_shield? "
                             "Check with simulate_fight on every enemy, then answer in 3 lines.")

bridge = (MCPBridge("http://127.0.0.1:8000/mcp") if "--http" in sys.argv
          else MCPBridge.stdio(ROOT / "modules/05_mcp/ember_mcp_server.py"))
try:
    tools = bridge.tools(read_only_names={"list_content", "get_entity", "simulate_fight", "balance_report",
                                          "validate_level_json", "propose_entity"})
    print("MCP tools discovered:", [t.name for t in tools])
    print("resource ember://enemies ->", bridge.read_resource("ember://enemies")[:120].replace("\n", " "), "...\n")

    agent = Agent(get_llm(), "You are Ember Crypt design assistant. Use tools for all facts. "
                             "For levels: draft JSON, call validate_level_json, fix errors, repeat until VALID, then save.",
                  tools, name="mcp-agent", max_turns=15, temperature=0.3)
    print(agent.run(task).text)
finally:
    bridge.close()
