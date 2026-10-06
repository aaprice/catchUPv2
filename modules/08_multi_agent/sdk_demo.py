"""M08.3 (optional) — Claude Agent SDK: Claude Code's loop as a Python library.

    uv sync --extra sdk
    uv run python modules/08_multi_agent/sdk_demo.py

Auth note: Anthropic docs direct SDK apps to use an API key (ANTHROPIC_API_KEY, console.anthropic.com, pay-per-use).
SDK drives the local Claude Code binary; on your own machine it may pick up your CLI login — personal
experimentation only. If it errors on auth, skip: studio_claude.py (claude -p) teaches the same ideas on Pro.

Shows: in-process MCP tools (@tool + create_sdk_mcp_server), programmatic subagents (AgentDefinition),
message stream (AssistantMessage / ResultMessage).
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from game import ContentDB  # noqa: E402
from game.world import simulate_fight  # noqa: E402

from claude_agent_sdk import (AgentDefinition, AssistantMessage, ClaudeAgentOptions, ResultMessage,  # noqa: E402
                              TextBlock, create_sdk_mcp_server, query, tool)

db = ContentDB()


@tool("duel", "Simulate base player + weapon/armor ids vs enemy id", {"enemy_id": str, "weapon_id": str, "armor_id": str})
async def duel(args):
    e = db.enemies.get(args["enemy_id"])
    if not e:
        return {"content": [{"type": "text", "text": f"unknown enemy; known {list(db.enemies)}"}], "is_error": True}
    w, a = db.items.get(args.get("weapon_id", "")), db.items.get(args.get("armor_id", ""))
    res = simulate_fight(4 + (w.power if w else 0), 1 + (a.power if a else 0), 30, e)
    return {"content": [{"type": "text", "text": json.dumps(res)}]}


async def main():
    server = create_sdk_mcp_server(name="arena", version="1.0.0", tools=[duel])   # MCP server IN your process
    options = ClaudeAgentOptions(
        cwd=str(ROOT),
        model="haiku",
        max_turns=12,
        mcp_servers={"arena": server},
        allowed_tools=["mcp__arena__duel", "Agent"],
        setting_sources=[],                           # don't load .claude/ config: fully programmatic harness
        agents={"balance-analyst": AgentDefinition(
            description="Runs duels and reports balance findings as a table.",
            prompt="You are a balance analyst. Use mcp__arena__duel for every number. Output a markdown table.",
            tools=["mcp__arena__duel"], model="haiku")},
    )
    prompt = ("Delegate to the balance-analyst subagent: duel every enemy with (rusty_sword,bone_shield) and "
              "(ember_blade,ash_mail). Then give me one sentence on the hardest enemy.")
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, TextBlock):
                    print("claude>", b.text)
        elif isinstance(msg, ResultMessage):
            print(f"\n[{msg.subtype}] turns={msg.num_turns} cost~${msg.total_cost_usd} usage={msg.usage}")


asyncio.run(main())
