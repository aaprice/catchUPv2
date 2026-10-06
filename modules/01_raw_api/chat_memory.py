"""M01.2 — "Memory" is just a list you resend. Prove it.

    uv run python modules/01_raw_api/chat_memory.py

Commands:  /forget  -> wipe history (model instantly "forgets")
           /dump    -> print exact messages list being sent
           /quit
Try: tell Mirela your name, chat 3 turns, ask her your name, then /forget and ask again.
Watch prompt-token count grow every turn: that's context growth = cost + latency growth.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import get_llm  # noqa: E402

shop = json.loads((Path(__file__).resolve().parents[2] / "game/data/shop.json").read_text())
SYSTEM = f"You are {shop['merchant']}. {shop['persona']} Keep replies under 40 words."

llm = get_llm()
history: list[dict] = []
print(f"[{llm}] Talk to {shop['merchant']}. /forget /dump /quit")
while True:
    user = input("\nyou> ").strip()
    if user == "/quit":
        break
    if user == "/forget":
        history.clear()
        print("(history wiped — next call sends only system + your message)")
        continue
    if user == "/dump":
        print(json.dumps([{"role": "system", "content": SYSTEM}, *history], indent=1))
        continue
    history.append({"role": "user", "content": user})
    reply = llm.chat([{"role": "system", "content": SYSTEM}, *history], temperature=0.8)
    history.append({"role": "assistant", "content": reply.text})
    print(f"mirela> {reply.text}")
    print(f"        \033[2m[{reply.usage.get('in')} prompt tok | {len(history)} msgs in history | {reply.latency_ms}ms]\033[0m")
