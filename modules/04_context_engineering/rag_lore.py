"""M04.1 — RAG over Ember Crypt lore. Three modes, same questions, compare honesty.

    uv run python modules/04_context_engineering/rag_lore.py --mode none
    uv run python modules/04_context_engineering/rag_lore.py --mode pipeline
    uv run python modules/04_context_engineering/rag_lore.py --mode agentic
    uv run python modules/04_context_engineering/rag_lore.py --mode pipeline --q "Who was Orrin Hale?"

none     = model answers from weights only        -> invents lore (hallucination demo)
pipeline = always retrieve top-k, stuff in prompt  -> classic RAG (workflow)
agentic  = model gets search_lore TOOL, decides when/what to search (agent) -> Claude Code style
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lib import Agent, Tracer, get_llm, tool  # noqa: E402
from lib.context import VectorStore, chunk_markdown  # noqa: E402

QUESTIONS = [
    "Why is the crypt called the Ember Crypt?",
    "What is the Gravewarden's weakness?",
    "Why does Mirela buy Cinder Charms?",
    "What hurts crypt dwellers?",
    "What color is Mirela's cart?",          # NOT in lore -> correct answer is "unknown"
]
RULES = "Answer in <=2 sentences. Cite sources like [03_gravewarden.md]. If lore doesn't say, answer 'The lore doesn't say.'"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["none", "pipeline", "agentic"], default="pipeline")
    ap.add_argument("--q", help="single question")
    ap.add_argument("--k", type=int, default=3)
    args = ap.parse_args()

    llm = get_llm()
    store = VectorStore(llm, cache=ROOT / "runs" / "lore_index.json")
    chunks = chunk_markdown(ROOT / "game/data/lore")
    if args.mode != "none":
        store.add(chunks)
        print(f"[{llm}] indexed {len(chunks)} chunks with {llm.embed_model}\n")

    for q in ([args.q] if args.q else QUESTIONS):
        print(f"Q: {q}")
        if args.mode == "none":
            ans = llm.chat([{"role": "system", "content": "You are Ember Crypt lore keeper. " + RULES},
                            {"role": "user", "content": q}], temperature=0.3).text
        elif args.mode == "pipeline":
            hits = store.search(q, k=args.k)
            for h in hits:
                print(f"   \033[2mretrieved {h['score']:.2f} {h['source']}: {h['text'][:70]}...\033[0m")
            ctx = "\n".join(f"<doc source='{h['source']}'>{h['text']}</doc>" for h in hits)
            ans = llm.chat([{"role": "system", "content": "You are Ember Crypt lore keeper. Use ONLY the docs. " + RULES},
                            {"role": "user", "content": f"<docs>\n{ctx}\n</docs>\n\nQuestion: {q}"}],
                           temperature=0.1).text
        else:
            @tool
            def search_lore(query: str) -> str:
                """Semantic search over Ember Crypt lore. Returns top passages with source file names.

                Args:
                    query: what to look for, in natural language
                """
                return "\n".join(f"[{h['source']}] {h['text']}" for h in store.search(query, k=args.k))

            agent = Agent(llm, "You are Ember Crypt lore keeper. Search lore before answering; you may search "
                               "multiple times with different phrasing. " + RULES,
                          [search_lore], name="lore", max_turns=5, temperature=0.1,
                          tracer=Tracer("lore", verbose=True))
            ans = agent.run(q).text
        print(f"A: {ans}\n")
    print(f"tokens: {llm.total_usage}")


if __name__ == "__main__":
    main()
