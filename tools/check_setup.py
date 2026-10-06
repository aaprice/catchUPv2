"""Environment check + model recommendation.  uv run python tools/check_setup.py"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.llm import load_env  # noqa: E402

load_env()
OK, BAD, WARN = "\033[32mOK\033[0m", "\033[31mMISSING\033[0m", "\033[33mWARN\033[0m"
if os.name == "nt":
    os.system("")


def run(cmd: list[str]) -> str | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return None


def main() -> None:
    print(f"python {sys.version.split()[0]}  {OK if sys.version_info >= (3, 11) else BAD + ' need 3.11+'}")
    for tool in ("git", "ollama", "opencode", "claude", "node", "npx", "llama-server"):
        print(f"{tool:<8} {OK if shutil.which(tool) else BAD}")

    vram_gb = None
    smi = run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if smi:
        name, mem = [s.strip() for s in smi.splitlines()[0].split(",")]
        vram_gb = int(mem) / 1024
        print(f"GPU      {name} {vram_gb:.1f} GB")
    else:
        print(f"GPU      {WARN} nvidia-smi not found; CPU inference will be slow")

    from lib.profiles import PROFILES, resolve
    fits = [n for n, p in PROFILES.items() if p["provider"] == "ollama" and p.get("vram_gb", 99) <= (vram_gb or 6) - 1]
    print(f"profiles that fit this GPU: {fits or ['gemma4-e4b (CPU/offload, slow)']}")
    print("  agent pick: largest of gemma4-26b > gpt-oss-20b > qwen3.5-9b > qwen3-8b > gemma4-e4b that fits")
    cfg = resolve(None)
    print(f"current: profile={cfg['profile']} model={cfg.get('model') or 'qwen3:8b (default)'} tool_mode={cfg.get('tool_mode')}")

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        tags = json.loads(urllib.request.urlopen(f"{host}/api/tags", timeout=5).read())
        have = [m["name"] for m in tags.get("models", [])]
        print(f"ollama   {OK} server up; models: {have}")
        for want in (cfg.get("model") or "qwen3:8b", os.getenv("EMBED_MODEL", "nomic-embed-text")):
            hit = any(h == want or h.split(":")[0] == want for h in have)
            print(f"  {want:<22} {OK if hit else BAD + f'  -> ollama pull {want}'}")
    except Exception as e:
        print(f"ollama   {BAD} server not reachable at {host} ({e}). Start Ollama app.")

    if shutil.which("opencode"):
        print("opencode run `opencode run \"say hi\"` once to confirm model wiring (see modules/06b_opencode)")


if __name__ == "__main__":
    main()
