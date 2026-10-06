"""PostToolUse(Edit|Write) hook: after Claude edits game content, validate it immediately.

Invalid -> JSON {"decision":"block","reason":...} -> Claude Code feeds reason to Claude, which fixes it.
= "sensor" in feedback loop: agent gets compiler-like error right after the bad write.
Same idea as lib/harness.py Hooks.post_tool.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

data = json.load(sys.stdin)
fp = data.get("tool_input", {}).get("file_path", "")
p = Path(fp)
try:
    rel = p.resolve().relative_to(ROOT / "game" / "data")
except (ValueError, OSError):
    sys.exit(0)                      # not game content -> nothing to check
if p.suffix != ".json" or p.name == "shop.json":
    sys.exit(0)

from game import ContentDB, Level, validate_json, validate_level  # noqa: E402

problems = []
try:
    db = ContentDB()                 # loads items.json + enemies.json (+ loot refs)
except Exception as e:
    problems.append(f"content DB failed to load: {e}")
    db = None

if db and p.name not in ("items.json", "enemies.json", "items_gen.json"):
    lv, errs = validate_json(Level, p.read_text(encoding="utf-8"))
    if errs:
        problems += errs
    else:
        rep = validate_level(lv, db)
        if not rep.ok:
            problems += rep.errors

if problems:
    print(json.dumps({"decision": "block",
                      "reason": f"{rel} is INVALID:\n- " + "\n- ".join(problems[:12]) + "\nFix and re-validate."}))
sys.exit(0)
