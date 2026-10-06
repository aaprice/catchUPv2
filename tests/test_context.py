from pathlib import Path

from lib import MockLLM
from lib.context import MemoryFile, VectorStore, chunk_markdown, est_tokens, make_compactor

ROOT = Path(__file__).resolve().parents[1]


def test_compactor_keeps_tail_and_no_orphan_tool():
    msgs = [{"role": "system", "content": "S"}]
    for i in range(10):
        msgs.append({"role": "user", "content": "x" * 400})
        msgs.append({"role": "assistant", "content": "", "tool_calls": [{"id": str(i), "name": "t", "arguments": {}}]})
        msgs.append({"role": "tool", "tool_call_id": str(i), "name": "t", "content": "y" * 400})
    out = make_compactor(MockLLM(["SUMMARY"]), budget_tokens=500, keep_last=5)(msgs)
    assert out[0]["content"] == "S" and "SUMMARY" in out[1]["content"]
    assert out[3]["role"] != "tool"
    assert est_tokens(out) < est_tokens(msgs)


def test_memory_file_dedup(tmp_path):
    m = MemoryFile(tmp_path / "m.md")
    assert m.append("likes axes") == "saved"
    assert m.append("Likes axes") == "already remembered"


def test_vector_store_mock(tmp_path):
    vs = VectorStore(MockLLM([]), cache=tmp_path / "idx.json")
    vs.add(chunk_markdown(ROOT / "game/data/lore"))
    hits = vs.search("Gravewarden Orrin iron key", k=2)
    assert len(hits) == 2 and all("source" in h for h in hits)
