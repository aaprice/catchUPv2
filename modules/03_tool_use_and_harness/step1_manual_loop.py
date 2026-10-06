"""M03.1 — Agent loop by hand. No framework. ~60 meaningful lines. Read top to bottom.

    uv run python modules/03_tool_use_and_harness/step1_manual_loop.py
    uv run python modules/03_tool_use_and_harness/step1_manual_loop.py "Which enemy gives best xp per hp lost with ember_blade?"
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from game import ContentDB, simulate_fight  # noqa: E402
from lib.llm import get_llm, tool_result_message  # noqa: E402

db = ContentDB()


# ---- 1. real functions ------------------------------------------------------
def get_enemy(enemy_id: str) -> str:
    e = db.enemies.get(enemy_id)
    return e.model_dump_json() if e else f"ERROR unknown enemy. Known ids: {list(db.enemies)}"


def get_item(item_id: str) -> str:
    i = db.items.get(item_id)
    return i.model_dump_json() if i else f"ERROR unknown item. Known ids: {list(db.items)}"


def fight(enemy_id: str, weapon_id: str = "", armor_id: str = "") -> str:
    e = db.enemies.get(enemy_id)
    if not e:
        return f"ERROR unknown enemy. Known ids: {list(db.enemies)}"
    w, a = db.items.get(weapon_id), db.items.get(armor_id)
    return json.dumps(simulate_fight(4 + (w.power if w else 0), 1 + (a.power if a else 0), 30, e))


REGISTRY = {"get_enemy": get_enemy, "get_item": get_item, "fight": fight}

# ---- 2. tool specs: what the MODEL sees (name + description + JSON schema) -------
TOOLS = [
    {"name": "get_enemy", "description": "Stats for one enemy (hp, atk, defense, xp, loot).",
     "parameters": {"type": "object", "properties": {"enemy_id": {"type": "string"}}, "required": ["enemy_id"]}},
    {"name": "get_item", "description": "Stats for one item (kind, power, value).",
     "parameters": {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"]}},
    {"name": "fight", "description": "Simulate player (30hp, base atk4 def1) vs enemy with optional gear. "
                                     "Returns turns_to_kill, hp_lost, player_survives.",
     "parameters": {"type": "object", "properties": {
         "enemy_id": {"type": "string"}, "weapon_id": {"type": "string"}, "armor_id": {"type": "string"}},
         "required": ["enemy_id"]}},
]

# ---- 3. THE LOOP ------------------------------------------------------------
question = sys.argv[1] if len(sys.argv) > 1 else \
    "Can a player with rusty_sword and bone_shield beat the gravewarden? How much hp is left?"
llm = get_llm()
messages = [
    {"role": "system", "content": "You are Ember Crypt balance analyst. Use tools for every number; never guess. "
                                  f"Enemy ids: {list(db.enemies)}. Item ids: {list(db.items)}."},
    {"role": "user", "content": question},
]

for turn in range(1, 9):                                     # hard cap: never loop forever
    reply = llm.chat(messages, tools=TOOLS, temperature=0.2)
    messages.append(reply.as_message())                     # assistant turn, incl. tool_calls
    if not reply.tool_calls:                                 # no tool calls => model is done
        print(f"\nFINAL (turn {turn}): {reply.text}")
        break
    for call in reply.tool_calls:
        fn = REGISTRY.get(call.name)
        try:
            result = fn(**call.arguments) if fn else f"ERROR no tool {call.name}"
        except TypeError as e:                               # model passed bad args -> tell it
            result = f"ERROR bad args: {e}"
        print(f"turn {turn}: {call.name}({call.arguments}) -> {result[:120]}")
        messages.append(tool_result_message(call, result))  # result goes back into context
else:
    print("hit max turns")

print(f"\ntokens: {llm.total_usage}   messages in context: {len(messages)}")
