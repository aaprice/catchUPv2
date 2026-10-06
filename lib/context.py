"""Context engineering helpers: token estimates, compaction, memory file, tiny vector store."""
from __future__ import annotations

import json
import math
from pathlib import Path


def est_tokens(messages: list[dict]) -> int:
    """~4 chars/token heuristic. Good enough for budgeting; real tokenizers differ ±20%."""
    n = 0
    for m in messages:
        n += len(m.get("content") or "") + len(json.dumps(m.get("tool_calls", ""))) + 8
    return n // 4


def make_compactor(llm, budget_tokens: int = 3000, keep_last: int = 6, tracer=None):
    """Returns fn(messages)->messages. When over budget: summarize middle, keep system + recent tail.

        [system, m1, m2, ... m20]  ──►  [system, summary(m1..m14), m15..m20]

    Gotcha: never split an assistant tool_call from its tool result (APIs reject orphans).
    """

    def compact(messages: list[dict]) -> list[dict]:
        if est_tokens(messages) <= budget_tokens or len(messages) <= keep_last + 2:
            return messages
        system, body = messages[0], messages[1:]
        cut = len(body) - keep_last
        while cut > 0 and body[cut]["role"] == "tool":     # don't orphan tool results
            cut -= 1
        old, recent = body[:cut], body[cut:]
        if not old:
            return messages
        transcript = "\n".join(f"{m['role']}: {(m.get('content') or '')[:600]}"
                               + (f" [called {[c['name'] for c in m['tool_calls']]}]" if m.get("tool_calls") else "")
                               for m in old)
        summary = llm.chat([{"role": "user", "content":
                             "Summarize this agent transcript for the agent itself to continue the task. Keep: "
                             "user goals, decisions, facts learned (numbers, ids), open questions. Drop chit-chat. "
                             f"Max 150 words.\n\n<transcript>\n{transcript}\n</transcript>"}],
                           temperature=0.1).text
        if tracer:
            tracer.event("compact", msg=f"summarized {len(old)} msgs -> {len(summary)} chars")
        return [system, {"role": "user", "content": f"[context summary of earlier conversation]\n{summary}"},
                {"role": "assistant", "content": "Understood, continuing."}, *recent]

    return compact


class MemoryFile:
    """Persistent agent memory = markdown file loaded into system prompt each session.
    Same mechanism as CLAUDE.md / GEMINI.md / Claude Code auto-memory. Dumb, effective."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8") if self.path.exists() else "(empty)"

    def append(self, fact: str) -> str:
        existing = self.read()
        if fact.strip().lower() in existing.lower():
            return "already remembered"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"- {fact.strip()}\n")
        return "saved"


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class VectorStore:
    """Smallest useful vector DB: list of (chunk, source, vector), brute-force cosine.
    Fine to ~10k chunks. Beyond: FAISS/pgvector/Chroma/etc. Same interface idea."""

    def __init__(self, llm, cache: Path | None = None):
        self.llm, self.cache = llm, cache
        self.rows: list[dict] = []

    def add(self, chunks: list[tuple[str, str]]) -> None:
        cached = {}
        if self.cache and self.cache.exists():
            cached = {(r["text"], r["source"]): r["vec"] for r in json.loads(self.cache.read_text())}
        todo = [c for c in chunks if c not in cached]
        if todo:
            vecs = self.llm.embed([t for t, _ in todo])
            cached.update({c: v for c, v in zip(todo, vecs)})
        self.rows = [{"text": t, "source": s, "vec": cached[(t, s)]} for t, s in chunks]
        if self.cache:
            self.cache.parent.mkdir(exist_ok=True)
            self.cache.write_text(json.dumps(self.rows))

    def search(self, query: str, k: int = 3) -> list[dict]:
        q = self.llm.embed([query])[0]
        scored = sorted(({**r, "score": cosine(q, r["vec"])} for r in self.rows), key=lambda r: -r["score"])
        return [{"text": r["text"], "source": r["source"], "score": round(r["score"], 3)} for r in scored[:k]]


def chunk_markdown(folder: Path) -> list[tuple[str, str]]:
    """Paragraph-level chunks w/ source. Chunking strategy = biggest RAG quality lever."""
    out = []
    for f in sorted(Path(folder).glob("*.md")):
        title = ""
        for para in f.read_text(encoding="utf-8").split("\n"):
            para = para.strip()
            if para.startswith("#"):
                title = para.lstrip("# ")
            elif para:
                out.append((f"[{title}] {para}", f.name))
    return out
