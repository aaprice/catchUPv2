"""Provider-agnostic LLM client. Zero third-party deps: raw HTTP so you SEE the wire format.

Providers (set LLM_PROVIDER in .env):
  ollama  -> native http://localhost:11434/api/chat   (local, free, default)
  openai  -> any OpenAI-compatible /chat/completions   (Gemini, LM Studio, vLLM on DGX, OpenRouter...)
  mock    -> scripted replies for tests (see MockLLM)

Internal message format = OpenAI chat style (de-facto lingua franca):
  {"role": "system"|"user"|"assistant"|"tool", "content": str,
   "tool_calls": [{"id","name","arguments"}]   # assistant only, our normalized form
   "tool_call_id": str, "name": str}           # tool only
Each adapter translates internal <-> wire. Classic Adapter pattern; same thing every harness
(Claude Code, LangChain, LiteLLM) does under the hood.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path = ROOT / ".env") -> None:
    """Tiny .env loader (KEY=VALUE lines). Real env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            v = v.split(" #")[0]                      # allow inline comments
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)      # {"in": n, "out": n}
    finish_reason: str = ""
    latency_ms: int = 0
    thinking: str = ""
    raw: dict = field(default_factory=dict)

    def as_message(self) -> dict:
        """Assistant message to append to history. MUST include tool_calls or the model loses track."""
        msg: dict[str, Any] = {"role": "assistant", "content": self.text}
        if self.tool_calls:
            msg["tool_calls"] = [{"id": c.id, "name": c.name, "arguments": c.arguments} for c in self.tool_calls]
        return msg


def tool_result_message(call: ToolCall, content: str) -> dict:
    return {"role": "tool", "tool_call_id": call.id, "name": call.name, "content": content}


THINK_RE = re.compile(r"<think>.*?</think>\s*", re.S)


def _post(url: str, payload: dict, headers: dict, timeout: int = 300, retries: int = 3) -> dict:
    body = json.dumps(payload).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:800]
            if e.code in (429, 500, 502, 503, 529) and attempt < retries:
                time.sleep(2 ** attempt * 2)          # exponential backoff: rate limits are normal life
                continue
            raise RuntimeError(f"HTTP {e.code} from {url}: {detail}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"cannot reach {url} ({e.reason}). Is the server running? See SETUP.md") from None
    raise RuntimeError("unreachable")


class LLM:
    def __init__(self, provider: str | None = None, model: str | None = None, profile: str | None = None,
                 tool_mode: str | None = None):
        """[v2] profile = name from lib/profiles.py (or LLM_PROFILE env). provider/model args override it."""
        from .profiles import resolve
        cfg = resolve(profile)
        self.profile = cfg["profile"]
        self.provider = provider or cfg["provider"]
        self.tool_mode = tool_mode or cfg.get("tool_mode", "native")
        if self.provider == "ollama":
            self.base = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
            self.model = model or cfg.get("model") or "qwen3:8b"
            self.num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "16384"))
        elif self.provider == "openai":
            self.base = (cfg.get("base") or os.getenv("OPENAI_BASE_URL")
                         or "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
            self.key = (cfg.get("key") or os.getenv(cfg.get("key_env", "OPENAI_API_KEY"))
                        or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY", "none"))
            self.model = model or cfg.get("model") or "gemini-flash-latest"
        else:
            raise ValueError(f"unknown provider {self.provider!r} (use ollama|openai, or MockLLM in tests)")
        if self.tool_mode not in ("native", "prompt"):
            raise ValueError("tool_mode must be native|prompt")
        self.embed_model = os.getenv("EMBED_MODEL", "nomic-embed-text" if self.provider == "ollama" else "gemini-embedding-001")
        self.total_usage = {"in": 0, "out": 0, "calls": 0}

    def __repr__(self) -> str:
        return f"LLM({self.provider}:{self.model}, tools={self.tool_mode}, profile={self.profile})"

    # ------------------------------------------------------------------ chat
    def chat(self, messages: list[dict], tools: list[dict] | None = None, schema: dict | None = None,
             temperature: float = 0.7, max_tokens: int | None = None) -> Reply:
        """One stateless call. The model remembers NOTHING between calls; `messages` IS its memory.

        tools  = list of {"name","description","parameters"(JSON Schema)}
        schema = JSON Schema -> constrained decoding (structured output)
        """
        t0 = time.time()
        if tools and self.tool_mode == "prompt":
            reply = self._chat_prompt_tools(messages, tools, temperature, max_tokens)
        elif self.provider == "ollama":
            reply = self._chat_ollama(messages, tools, schema, temperature, max_tokens)
        else:
            reply = self._chat_openai(messages, tools, schema, temperature, max_tokens)
        reply.latency_ms = int((time.time() - t0) * 1000)
        self.total_usage["in"] += reply.usage.get("in", 0)
        self.total_usage["out"] += reply.usage.get("out", 0)
        self.total_usage["calls"] += 1
        return reply

    def _chat_ollama(self, messages, tools, schema, temperature, max_tokens) -> Reply:
        wire = []
        for m in messages:
            w = {"role": m["role"], "content": m.get("content") or ""}
            if m.get("tool_calls"):
                w["tool_calls"] = [{"function": {"name": c["name"], "arguments": c["arguments"]}} for c in m["tool_calls"]]
            if m["role"] == "tool":
                w["tool_name"] = m.get("name", "")
            wire.append(w)
        payload: dict[str, Any] = {
            "model": self.model, "messages": wire, "stream": False,
            "options": {"temperature": temperature, "num_ctx": self.num_ctx},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
        if schema:
            payload["format"] = schema
        if os.getenv("LLM_THINK") in ("0", "1"):
            payload["think"] = os.getenv("LLM_THINK") == "1"
        data = _post(f"{self.base}/api/chat", payload, {})
        msg = data.get("message", {})
        calls = []
        for c in msg.get("tool_calls") or []:
            fn = c.get("function", {})
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                args = _loads_lenient(args)
            calls.append(ToolCall(id=c.get("id") or f"call_{uuid.uuid4().hex[:8]}", name=fn.get("name", ""), arguments=args))
        text = msg.get("content") or ""
        thinking = msg.get("thinking") or "".join(THINK_RE.findall(text))
        return Reply(text=THINK_RE.sub("", text).strip(), tool_calls=calls, thinking=thinking,
                     usage={"in": data.get("prompt_eval_count", 0), "out": data.get("eval_count", 0)},
                     finish_reason=data.get("done_reason", ""), raw=data)

    def _chat_openai(self, messages, tools, schema, temperature, max_tokens) -> Reply:
        wire = []
        for m in messages:
            w: dict[str, Any] = {"role": m["role"], "content": m.get("content") or ""}
            if m.get("tool_calls"):
                w["tool_calls"] = [{"id": c["id"], "type": "function",
                                    "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                                   for c in m["tool_calls"]]
            if m["role"] == "tool":
                w["tool_call_id"] = m["tool_call_id"]
            wire.append(w)
        payload: dict[str, Any] = {"model": self.model, "messages": wire, "temperature": temperature}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
        if schema:
            payload["response_format"] = {"type": "json_schema",
                                          "json_schema": {"name": "output", "schema": schema}}
        data = _post(f"{self.base}/chat/completions", payload, {"Authorization": f"Bearer {self.key}"})
        choice = data["choices"][0]
        msg = choice["message"]
        calls = [ToolCall(id=c.get("id") or f"call_{uuid.uuid4().hex[:8]}", name=c["function"]["name"],
                          arguments=_loads_lenient(c["function"].get("arguments") or "{}"))
                 for c in msg.get("tool_calls") or []]
        text = msg.get("content") or ""
        u = data.get("usage") or {}
        return Reply(text=THINK_RE.sub("", text).strip(), tool_calls=calls,
                     usage={"in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0)},
                     finish_reason=choice.get("finish_reason", ""), raw=data)

    # ------------------------------------------------------- [v2] prompt-mode tool calling
    def _chat_prompt_tools(self, messages, tools, temperature, max_tokens) -> Reply:
        """Tool calling WITHOUT native support. Harness does what the chat template normally does:
          1. describe tools in system prompt (text)
          2. force reply into JSON schema {action: call|final, calls:[{name, arguments}], text}
             -> constrained decoding guarantees parseable JSON, enum guarantees valid tool names
          3. parse JSON -> ToolCall objects; history re-encoded as plain user/assistant text
        Same Reply shape out, so lib/harness.py doesn't know or care which mode ran.
        """
        names = [t["name"] for t in tools]
        schema = {"type": "object", "required": ["action"], "properties": {
            "action": {"type": "string", "enum": ["call", "final"]},
            "calls": {"type": "array", "items": {"type": "object", "required": ["name", "arguments"], "properties": {
                "name": {"type": "string", "enum": names}, "arguments": {"type": "object"}}}},
            "text": {"type": "string"}}}
        catalog = "\n".join(f"- {t['name']}: {t['description']}\n  args schema: {json.dumps(t['parameters'])}"
                             for t in tools)
        protocol = ("\n\n<tools>\n" + catalog + "\n</tools>\n"
                    "Reply ONLY with JSON. To use tools: {\"action\":\"call\",\"calls\":[{\"name\":...,\"arguments\":{...}}]}. "
                    "When finished: {\"action\":\"final\",\"text\":\"<answer for the user>\"}. "
                    "Tool results arrive as messages starting with [tool_result].")
        wire: list[dict] = []
        for m in messages:
            if m["role"] == "system":
                wire.append({"role": "system", "content": (m.get("content") or "") + protocol})
            elif m["role"] == "tool":
                wire.append({"role": "user", "content": f"[tool_result {m.get('name', '')}] {m.get('content', '')}"})
            elif m["role"] == "assistant" and m.get("tool_calls"):
                wire.append({"role": "assistant", "content": json.dumps(
                    {"action": "call", "calls": [{"name": c["name"], "arguments": c["arguments"]} for c in m["tool_calls"]]})})
            elif m["role"] == "assistant":
                wire.append({"role": "assistant", "content": json.dumps({"action": "final", "text": m.get("content") or ""})})
            else:
                wire.append({"role": m["role"], "content": m.get("content") or ""})
        if not any(m["role"] == "system" for m in wire):
            wire.insert(0, {"role": "system", "content": protocol.strip()})
        inner = self._chat_ollama if self.provider == "ollama" else self._chat_openai
        r = inner(wire, None, schema, temperature, max_tokens)
        data = _loads_lenient(r.text)
        if data.get("action") == "call" and data.get("calls"):
            r.tool_calls = [ToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=c.get("name", ""),
                                     arguments=c.get("arguments") or {}) for c in data["calls"]]
            r.text = ""
        else:
            r.text = data.get("text") or r.text
        return r

    # ------------------------------------------------------------- embeddings
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Text -> vectors. Similar meaning => nearby vectors. Basis of RAG (module 04)."""
        if self.provider == "ollama":
            data = _post(f"{self.base}/api/embed", {"model": self.embed_model, "input": texts}, {})
            return data["embeddings"]
        data = _post(f"{self.base}/embeddings", {"model": self.embed_model, "input": texts},
                     {"Authorization": f"Bearer {self.key}"})
        return [d["embedding"] for d in data["data"]]


def _loads_lenient(s: str) -> dict:
    """Small models emit sloppy JSON. Be liberal in what you accept, strict in what you execute."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"_unparsed": s}


class MockLLM:
    """Scripted stand-in. Each entry: Reply, str (text reply), or fn(messages, tools) -> Reply.
    Lets you unit-test harness logic deterministically, no GPU, no cost."""

    def __init__(self, script: list[Reply | str | Callable[[list[dict], list[dict] | None], Reply]]):
        self.script = list(script)
        self.calls: list[dict] = []
        self.model, self.provider = "mock", "mock"
        self.total_usage = {"in": 0, "out": 0, "calls": 0}

    def chat(self, messages, tools=None, schema=None, temperature=0.7, max_tokens=None) -> Reply:
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools, "schema": schema})
        self.total_usage["calls"] += 1
        if not self.script:
            return Reply(text="(mock script exhausted)")
        nxt = self.script.pop(0)
        if callable(nxt):
            return nxt(messages, tools)
        return Reply(text=nxt) if isinstance(nxt, str) else nxt

    def embed(self, texts: list[str]) -> list[list[float]]:
        # bag-of-letters vectors: crude but deterministic; enough to test RAG plumbing
        return [[t.lower().count(ch) for ch in "abcdefghijklmnopqrstuvwxyz"] for t in texts]


def get_llm(**kw) -> LLM:
    return LLM(**kw)
