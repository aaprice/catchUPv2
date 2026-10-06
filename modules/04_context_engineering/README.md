# M04 — Context engineering

Goal: control *what's in the window*. 2025's big realization: most agent failures = context failures, not model failures.

## Analogy

Context window = **workbench**. Small, finite. Everything model uses must be on bench *right now*.
- Clutter (old tool dumps, irrelevant docs) → worse work + slower + pricier ("context rot").
- Missing part (no lore, no player prefs) → model improvises (hallucination).
- Context engineering = **bench management**: fetch right part just-in-time, clear junk, keep notebook of decisions.

## Four levers

```
                ┌──────────────── context window ─────────────────┐
  WRITE ──────► │ system │ tools │ memory │ retrieved │ history   │ ◄── SELECT (RAG, search tools)
 (memory files) │ prompt │ specs │  file  │   docs    │ + results │
                └─────────────────────────────────────────────────┘
  COMPRESS ───► summarize/trim old history          ISOLATE ───► push work into sub-agent w/ own window (M08)
```

| Lever | What | Here | Claude Code |
|---|---|---|---|
| **Write** | persist facts outside window | `MemoryFile` → `memory/advisor.md` | `CLAUDE.md`, auto-memory, `#` shortcut |
| **Select** | pull relevant info in | `rag_lore.py` (pipeline vs agentic) | Grep/Glob/Read tools = agentic search; skills load on demand |
| **Compress** | shrink history | `make_compactor()` | auto-compact, `/compact` |
| **Isolate** | separate windows | M08 workers | subagents, `context: fork` skills |

## RAG in one picture

```
 INDEX (once):  lore/*.md → chunk (paragraphs) → embed → vectors[] (runs/lore_index.json)
 QUERY:         question → embed → cosine top-k → paste chunks in prompt → answer w/ citations
```

Embeddings = coordinates in "meaning space". "What hurts wraiths?" lands near "Cold iron does [harm crypt dwellers]" despite no shared keywords.

**Pipeline RAG vs agentic RAG:**
- Pipeline: always retrieve, once. Cheap, predictable. Misses multi-hop ("Who locked the Gravewarden in, and how is she related to Mirela?").
- Agentic: search is a *tool*; model reformulates, searches twice, combines. Claude Code doesn't use vector DB at all for code — it greps like you. Agentic search + good tools often beats embeddings for code/structured data.

## Compaction

```
 [sys, u1, a1, t1, a2, ..., u9, a9]    est 3.4k tok > budget 3k
            └─────summarize──────┘
 [sys, "[summary] player wants glass cannon, has 50g, asked about warden...", ack, u8, a8, u9, a9]
```
Gotchas: never orphan tool results; summaries lose detail (→ also write key facts to memory file); summary call costs tokens too.

## Prefix caching

Providers cache KV state of prompt prefixes. Hit = ~10× cheaper + faster input. Rule: **stable first, volatile last.** `cache_demo.py` shows Ollama prompt_eval_count collapse on repeated prefix.

## Run

```powershell
uv run python modules/04_context_engineering/rag_lore.py --mode none       # watch it invent lore
uv run python modules/04_context_engineering/rag_lore.py --mode pipeline
uv run python modules/04_context_engineering/rag_lore.py --mode agentic
uv run python modules/04_context_engineering/memory_agent.py               # twice
uv run python modules/04_context_engineering/cache_demo.py
```

Check last question ("cart color") — correct = "lore doesn't say". `none` mode usually invents.

## Context budget checklist (use on every agent you build)

- [ ] System prompt < ~1.5k tokens; rules not essays.
- [ ] Tool outputs capped/truncated; paginate big results.
- [ ] Docs retrieved just-in-time, not preloaded "just in case".
- [ ] Long tasks: memory/progress file the agent updates (Ralph loops rely on this — M07).
- [ ] Subtasks with big intermediate junk → sub-agent, return only summary.
- [ ] Stable prefix ordering for cache hits.

## Exercises

- ★ Change chunking to whole files instead of paragraphs. Retrieval quality on Q2/Q3?
- ★ Add `forget(fact)` tool to memory agent. Should it need human approval? Why?
- ★★ Hybrid search: score = 0.7·cosine + 0.3·keyword overlap. Test on "Orrin" (rare proper noun — embeddings often weak on names).
- ★★ Shopkeeper (M03) + `search_lore` tool → Mirela gossips about Gravewarden with citations.
- ★★★ Measure "context rot": stuff 20k tokens of irrelevant junk before lore question; compare accuracy over 10 runs vs clean context (set `OLLAMA_NUM_CTX=32768`).

Next: [M05 MCP](../05_mcp/).
