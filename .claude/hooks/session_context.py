"""SessionStart hook: stdout becomes context for Claude. Inject current learning position + repo state.
Dynamic context injection = cheap, always-fresh alternative to stuffing CLAUDE.md."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
prog = (ROOT / "PROGRESS.md").read_text(encoding="utf-8") if (ROOT / "PROGRESS.md").exists() else ""
todo = [m.group(1) for m in re.finditer(r"- \[ \] (.+)", prog)]
done = len(re.findall(r"- \[x\]", prog, re.I))
status = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
print(f"[CatchUP] learner progress: {done} done; next up: {todo[0] if todo else 'all done'}")
print(f"[CatchUP] git changes:\n{status[:800] or '(clean)'}")
