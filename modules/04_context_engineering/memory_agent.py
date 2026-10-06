"""M04.2 — Persistent memory across sessions via a markdown file (CLAUDE.md pattern).

    uv run python modules/04_context_engineering/memory_agent.py      # session 1: tell it your playstyle
    uv run python modules/04_context_engineering/memory_agent.py      # session 2: it remembers
    type memory\\advisor.md                                          # inspect / edit memory by hand

Run 1: "I always play glass-cannon: max weapon, no armor. I hate potions."
Run 2: "What should I buy before the gravewarden?"  -> advice should respect stored prefs.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from game import ContentDB  # noqa: E402
from lib import Agent, get_llm, tool  # noqa: E402
from lib.context import MemoryFile, make_compactor  # noqa: E402
from lib.game_tools import Shop  # noqa: E402

mem = MemoryFile(ROOT / "memory" / "advisor.md")
shop = Shop(ContentDB())


@tool(read_only=False)
def remember(fact: str) -> str:
    """Save a durable fact about the player (preferences, playstyle, goals) for future sessions.
    Only durable facts, not chit-chat.

    Args:
        fact: one short sentence, e.g. 'Player prefers glass-cannon builds (no armor).'
    """
    return mem.append(fact)


tools = [remember] + [t for t in shop.tools() if t.read_only]   # advisor can't sell
llm = get_llm()
system = f"""You are the Ember Crypt build advisor. Help the player plan gear vs enemies using tools.
When the player reveals a durable preference, call remember().
<player_memory>
{mem.read()}
</player_memory>
Respect player_memory in all advice. Under 80 words."""

agent = Agent(llm, system, tools, name="advisor", policy=lambda t, c: "allow",
              compactor=make_compactor(llm, budget_tokens=2500, keep_last=6))
print(f"[{llm}] memory loaded from {mem.path}:\n{mem.read()}\n(/quit)")
history: list[dict] = []
while (user := input("\nyou> ").strip()) not in ("/quit", "q"):
    res = agent.run(user, history)
    history = res.messages[1:]
    print(f"\nadvisor> {res.text}")
