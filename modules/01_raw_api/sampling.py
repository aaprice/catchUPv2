"""M01.3 — Temperature. Same prompt, different randomness.

    uv run python modules/01_raw_api/sampling.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import get_llm  # noqa: E402

llm = get_llm()
PROMPT = "Invent ONE name for a new crypt monster. Reply with the name only, 1-3 words."
msgs = [{"role": "user", "content": PROMPT}]

for temp in (0.0, 0.7, 1.4):
    names = [llm.chat(msgs, temperature=temp, max_tokens=400).text.strip().split("\n")[0] for _ in range(4)]
    print(f"temp {temp:>3}: {names}")

print("""
Observe:
  0.0 -> (near) identical every time. Use for: tool use, extraction, judges, code.
  0.7 -> varied but sane. Use for: dialogue, content gen.
  1.4 -> weird, sometimes broken. Rarely useful; breaks JSON/tool calls first.
Implication: one run proves nothing. Measure distributions (M09 evals).""")
