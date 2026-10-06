"""[v2] Model profiles: one name -> provider + model + quirks. Pick with LLM_PROFILE=<name> in .env.

Why profiles: every open model has quirks (tool-call format, thinking toggle, context needs). Encoding
quirks in config instead of scattering if-statements = same idea as a DB dialect table.

tool_mode:
  native = server parses model's tool-call tokens into tool_calls (fast, needs good template support)
  prompt = harness describes tools in prompt + forces JSON via schema; harness parses calls itself.
           Slower, but works with ANY model that supports JSON-schema output. Fallback for flaky tool
           templates (e.g. small Gemma builds, older Ollama/llama.cpp parsers).
Env vars still override individual fields (LLM_MODEL, OLLAMA_HOST, OPENAI_BASE_URL, LLM_TOOL_MODE...).
"""
from __future__ import annotations

import os

PROFILES: dict[str, dict] = {
    # ---------- Ollama (home PC or work workstation) ----------
    "qwen3-8b":      {"provider": "ollama", "model": "qwen3:8b",     "tool_mode": "native", "vram_gb": 8},
    "qwen3.5-9b":    {"provider": "ollama", "model": "qwen3.5:9b",   "tool_mode": "native", "vram_gb": 8},
    "gemma4-e4b":    {"provider": "ollama", "model": "gemma4:e4b",   "tool_mode": "prompt", "vram_gb": 8,
                      "note": "small Gemma: prompt-mode tools usually more reliable than native"},
    "gemma4-12b":    {"provider": "ollama", "model": "gemma4:12b",   "tool_mode": "native", "vram_gb": 10},
    "gemma4-26b":    {"provider": "ollama", "model": "gemma4:26b",   "tool_mode": "native", "vram_gb": 18,
                      "note": "MoE ~4B active: big-model quality, small-model speed. Best Gemma for agents"},
    "gemma4-31b":    {"provider": "ollama", "model": "gemma4:31b",   "tool_mode": "native", "vram_gb": 22},
    "gpt-oss-20b":   {"provider": "ollama", "model": "gpt-oss:20b",  "tool_mode": "native", "vram_gb": 16},
    "qwen3-coder-30b": {"provider": "ollama", "model": "qwen3-coder:30b", "tool_mode": "native", "vram_gb": 20},
    # ---------- OpenAI-compatible servers ----------
    "llamacpp":      {"provider": "openai", "base": "http://127.0.0.1:8080/v1", "model": "local", "key": "none",
                      "tool_mode": "native",
                      "note": "llama-server -m model.gguf --jinja -c 32768  (--jinja REQUIRED for tool calls)"},
    "lmstudio":      {"provider": "openai", "base": "http://127.0.0.1:1234/v1", "model": "local", "key": "none",
                      "tool_mode": "native"},
    "dgx-vllm":      {"provider": "openai", "base": "http://dgx:8000/v1", "model": "google/gemma-4-26b-it",
                      "key": "EMPTY", "tool_mode": "native",
                      "note": "vllm serve <model> --enable-auto-tool-choice --tool-call-parser <gemma4|hermes|...>"},
    "gemini":        {"provider": "openai", "base": "https://generativelanguage.googleapis.com/v1beta/openai",
                      "model": "gemini-flash-latest", "key_env": "GEMINI_API_KEY", "tool_mode": "native"},
}


def resolve(name: str | None = None) -> dict:
    """Return config for profile `name` (or LLM_PROFILE env). No profile -> legacy LLM_PROVIDER/LLM_MODEL env.

    With a profile, LLM_PROVIDER/LLM_MODEL are IGNORED (avoids stale .env values silently winning).
    Allowed overrides: LLM_TOOL_MODE; DGX_URL/DGX_MODEL (dgx-vllm); OPENAI_BASE_URL (llamacpp/lmstudio).
    """
    name = name or os.getenv("LLM_PROFILE") or None
    if name:
        if name not in PROFILES:
            raise ValueError(f"unknown profile {name!r}. Known: {sorted(PROFILES)}")
        cfg = dict(PROFILES[name])
        if name == "dgx-vllm":
            cfg["base"] = os.getenv("DGX_URL", cfg["base"])
            cfg["model"] = os.getenv("DGX_MODEL", cfg["model"])
        if name in ("llamacpp", "lmstudio") and os.getenv("OPENAI_BASE_URL"):
            cfg["base"] = os.getenv("OPENAI_BASE_URL")
    else:
        cfg = {"provider": os.getenv("LLM_PROVIDER", "ollama"), "model": os.getenv("LLM_MODEL"), "tool_mode": "native"}
    if os.getenv("LLM_TOOL_MODE"):
        cfg["tool_mode"] = os.getenv("LLM_TOOL_MODE")
    cfg["profile"] = name or "(env)"
    return cfg
