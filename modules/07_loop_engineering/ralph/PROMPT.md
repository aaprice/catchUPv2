# Ralph iteration prompt (fed fresh every iteration — you have NO memory of earlier iterations)

You are implementing game features for Ember Crypt, one per iteration.

1. Read `modules/07_loop_engineering/ralph/NOTES.md` (learnings from earlier iterations) and
   `modules/07_loop_engineering/ralph/FEATURES.md` (backlog).
2. Pick the FIRST unchecked feature `- [ ]`. Only that one.
3. Write tests first in `tests/test_features.py` (create if missing) encoding its acceptance criteria.
4. Implement in `game/` (keep game/ pure: no I/O, no randomness). Keep existing tests green.
5. Run `uv run pytest -q`. Iterate until ALL tests pass. Do not delete or weaken existing tests.
6. Tick the box in FEATURES.md (`- [x]`). Append 1-3 lines of learnings/gotchas to NOTES.md.
7. `git add -A` and `git commit -m "ralph: <feature name>"`.
8. If every box in FEATURES.md is checked, write the single line `RALPH_DONE` at end of NOTES.md.

Stop after one feature. Be concise in your final message: feature, tests added, result.
