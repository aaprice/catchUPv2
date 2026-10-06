"""M01.1 — Raw HTTP. No SDK. See exact bytes going over wire.

    uv run python modules/01_raw_api/hello.py
    uv run python modules/01_raw_api/hello.py "Name three crypt monsters"
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.llm import load_env  # noqa: E402
from lib.profiles import resolve  # noqa: E402  [v2]  (only reads .env; no SDK)

load_env()
HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
_cfg = resolve(None)
MODEL = _cfg.get("model") or "qwen3:8b"   # [v2] profile-aware
if _cfg.get("provider") != "ollama":
    sys.exit(f"hello.py speaks raw Ollama API; profile {_cfg['profile']} is {_cfg['provider']}. "
             "Try modules/01_raw_api/chat_memory.py (uses lib adapters) or exercise 'hello_openai.py'.")
prompt = sys.argv[1] if len(sys.argv) > 1 else "In one sentence: what is a roguelike?"

request_body = {
    "model": MODEL,
    "messages": [                                    # ENTIRE conversation every time (stateless!)
        {"role": "system", "content": "You are terse game-design expert. Max 2 sentences."},
        {"role": "user", "content": prompt},
    ],
    "stream": False,                                 # True = tokens arrive as NDJSON chunks
    "options": {"temperature": 0.7, "num_ctx": 8192},
}
if MODEL.startswith(("qwen3", "gpt-oss")):
    request_body["think"] = False                    # reasoning off for speed. Gemma 4: thinking already off by default

print("=== REQUEST  POST", f"{HOST}/api/chat")
print(json.dumps(request_body, indent=2))

req = urllib.request.Request(f"{HOST}/api/chat", data=json.dumps(request_body).encode(),
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=300) as r:
    resp = json.loads(r.read())

print("\n=== RESPONSE (trimmed)")
print(json.dumps({k: resp[k] for k in ("model", "message", "done_reason", "prompt_eval_count", "eval_count",
                                       "total_duration") if k in resp}, indent=2))
tps = resp.get("eval_count", 0) / max(resp.get("eval_duration", 1) / 1e9, 1e-9)
print(f"\n{resp.get('prompt_eval_count')} prompt tokens, {resp.get('eval_count')} output tokens, ~{tps:.0f} tok/s")
print("\nThat's the whole API. Every SDK/agent/harness = layers on top of this POST.")
