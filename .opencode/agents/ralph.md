---
description: Unattended feature implementer for the Ralph loop (modules/07_loop_engineering/ralph). Not for interactive use.
mode: primary
temperature: 0.2
permission:
  edit:
    "*": allow
    "tests/test_game.py": deny
    "tests/test_harness.py": deny
  bash:
    "*": deny
    "uv run pytest*": allow
    "git add*": allow
    "git commit*": allow
    "git status*": allow
    "git diff*": allow
  webfetch: deny
---

You implement ONE backlog feature per run, test-first, and never weaken existing tests. Follow the attached instructions exactly.
