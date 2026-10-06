"""M04.3 — Prefix caching: same prefix = cheap/fast. Change 1 char early = full recompute.

    uv run python modules/04_context_engineering/cache_demo.py

Ollama keeps KV-cache of last prompt for loaded model; matching prefix tokens skip prompt evaluation.
Anthropic/OpenAI/Gemini do same at scale (prompt caching: ~90% cheaper cached input tokens).
Lesson: order context STABLE -> VOLATILE. System prompt + tool defs + docs first; user turn last.
Never put timestamps / random ids at top of system prompt.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lib.llm import load_env  # noqa: E402
from lib.profiles import resolve  # noqa: E402  [v2]

load_env()
HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = resolve(None).get("model") or "qwen3:8b"   # [v2] profile-aware (Ollama profiles only)
LORE = "\n\n".join(p.read_text() for p in sorted((ROOT / "game/data/lore").glob("*.md")))
BIG_SYSTEM = "You are lore keeper. Answer in 5 words.\n<lore>\n" + LORE * 3 + "\n</lore>"


def call(system: str, q: str) -> tuple[int, float]:
    body = {"model": MODEL, "stream": False, "options": {"num_ctx": 8192, "num_predict": 30},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": q}]}
    req = urllib.request.Request(f"{HOST}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    return r.get("prompt_eval_count", 0), r.get("prompt_eval_duration", 0) / 1e6


runs = [("cold", BIG_SYSTEM, "Who is Mirela?"),
        ("same prefix, new question", BIG_SYSTEM, "Who is Orrin?"),
        ("same prefix again", BIG_SYSTEM, "What hurts wraiths?"),
        ("prefix changed at char 0", "Today is Tuesday. " + BIG_SYSTEM, "Who is Orrin?")]
for label, sys_p, q in runs:
    n, ms = call(sys_p, q)
    print(f"{label:<28} prompt_eval_count={n:>5}  prompt_eval={ms:8.1f} ms")
print("\nCache hit on runs 2-3 shows as much lower prompt_eval ms (and, on most Ollama versions, lower prompt_eval_count).")
