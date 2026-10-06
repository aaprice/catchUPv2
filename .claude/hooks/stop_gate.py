"""Stop hook: back-pressure. Claude wants to finish -> if code changed and tests fail, say "not done".

OPT-IN: create file .claude/stop_gate.on to enable (PowerShell: New-Item .claude/stop_gate.on).
Loop-safety: Claude Code sets stop_hook_active=true when already continuing due to a stop hook;
we then allow stopping to avoid infinite loops. Mirrors lib/harness.py Hooks.on_stop + max_stop_retries.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
data = json.load(sys.stdin)
if not (ROOT / ".claude" / "stop_gate.on").exists() or data.get("stop_hook_active"):
    sys.exit(0)

changed = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
if not any(line.strip().endswith(".py") for line in changed.splitlines()):
    sys.exit(0)                      # no python changes -> nothing to verify

r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x"], cwd=ROOT, capture_output=True, text=True)
if r.returncode != 0:
    tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-25:])
    print(json.dumps({"decision": "block",
                      "reason": f"Tests failing; you are not done. Fix, then finish.\n{tail}"}))
sys.exit(0)
