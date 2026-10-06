"""Bridge: connect YOUR sync harness to any MCP server (stdio or HTTP) -> list[Tool].

This is exactly what Claude Code / Gemini CLI do internally:
  1. spawn/connect server   2. initialize   3. tools/list   4. expose to model as tools
  5. on tool call -> tools/call over JSON-RPC -> paste result into context

Async MCP client runs on a background event loop thread; sync wrappers submit coroutines to it.
"""
from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path

from mcp import Client, StdioServerParameters

from .tools import Tool


class MCPBridge:
    def __init__(self, target: str | StdioServerParameters | object, prefix: str = ""):
        """target: URL 'http://127.0.0.1:8000/mcp', StdioServerParameters, or in-process MCPServer (tests)."""
        self.target, self.prefix = target, prefix
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.client: Client | None = None
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._life = asyncio.run_coroutine_threadsafe(self._lifecycle(), self.loop)
        if not self._ready.wait(60) or self._error:
            raise RuntimeError(f"MCP connect failed: {self._error!r}")

    @classmethod
    def stdio(cls, script: str | Path, prefix: str = "") -> "MCPBridge":
        return cls(StdioServerParameters(command=sys.executable, args=[str(script)]), prefix)

    async def _lifecycle(self):
        # anyio rule: context must be entered + exited in SAME task -> one long-lived task owns it
        self._stop = asyncio.Event()
        try:
            async with Client(self.target) as c:
                self.client = c
                self._ready.set()
                await self._stop.wait()
        except BaseException as e:   # surface connect errors to constructor
            self._error = e
            self._ready.set()

    def _run(self, coro, timeout: float = 120):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self._stop.set)
        try:
            self._life.result(15)
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)

    # ---- MCP -> harness Tool objects ------------------------------------------
    def tools(self, read_only_names: set[str] | None = None) -> list[Tool]:
        listed = self._run(self.client.list_tools()).tools
        out = []
        for t in listed:
            schema = dict(t.input_schema or {"type": "object", "properties": {}})
            schema.pop("title", None)
            ann = t.annotations
            ro = (t.name in read_only_names) if read_only_names is not None else bool(ann and ann.read_only_hint)
            out.append(Tool(name=self.prefix + t.name, description=t.description or "", parameters=schema,
                            fn=self._caller(t.name), read_only=ro))
        return out

    def _caller(self, name: str):
        def call(**kwargs) -> str:
            res = self._run(self.client.call_tool(name, kwargs))
            text = "\n".join(getattr(c, "text", str(c)) for c in res.content)
            return ("ERROR: " + text) if res.is_error else text
        return call

    def read_resource(self, uri: str) -> str:
        res = self._run(self.client.read_resource(uri))
        return "\n".join(getattr(c, "text", "") for c in res.contents)

    def get_prompt(self, name: str, args: dict) -> str:
        res = self._run(self.client.get_prompt(name, args))
        return "\n".join(getattr(m.content, "text", "") for m in res.messages)
