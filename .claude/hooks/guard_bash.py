"""PreToolUse(Bash) hook: deterministic guardrail + audit log.

Claude Code sends JSON on stdin: {"tool_name":"Bash","tool_input":{"command":"..."}, ...}
exit 0            -> no opinion, normal permission flow
exit 2 + stderr   -> BLOCK; stderr text is shown to Claude so it can pick another approach
Same idea as lib/harness.py Hooks.pre_tool, but enforced by Claude Code.
"""
import json
import re
import sys
import time
from pathlib import Path

data = json.load(sys.stdin)
cmd = data.get("tool_input", {}).get("command", "")

log = Path(__file__).resolve().parents[2] / "runs" / "bash_audit.log"
log.parent.mkdir(exist_ok=True)
with log.open("a", encoding="utf-8") as f:
    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{cmd}\n")

BLOCK = [
    (r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r", "recursive force delete"),
    (r"git\s+push\b.*(--force|-f\b)", "force push"),
    (r"git\s+reset\s+--hard", "hard reset discards work; use git stash"),
    (r"Remove-Item\b.*-Recurse", "recursive delete (PowerShell)"),
    (r"(curl|wget|iwr|Invoke-WebRequest)\b.*\|\s*(sh|bash|iex|python)", "pipe-download-to-shell"),
    (r"(>|sed\s+-i|\btee\b|Set-Content|Out-File|\bmv\s).*game[/\\]data[/\\](items|enemies|level_01)\.json",
     "core content written via shell; use Edit/Write tools so validation hook runs"),
]
for pattern, why in BLOCK:
    if re.search(pattern, cmd, re.I):
        print(f"Blocked by .claude/hooks/guard_bash.py: {why}. Command: {cmd}", file=sys.stderr)
        sys.exit(2)
sys.exit(0)
