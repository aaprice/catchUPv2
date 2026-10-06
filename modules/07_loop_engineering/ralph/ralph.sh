#!/usr/bin/env bash
# Ralph loop (Git Bash / Linux). Same as ralph.ps1. Usage: bash modules/07_loop_engineering/ralph/ralph.sh 5 sonnet
set -euo pipefail
MAX=${1:-5}; MODEL=${2:-sonnet}
cd "$(git rev-parse --show-toplevel)"
DIR=modules/07_loop_engineering/ralph
git switch ralph 2>/dev/null || git switch -c ralph
mkdir -p runs
for i in $(seq 1 "$MAX"); do
  grep -q RALPH_DONE "$DIR/NOTES.md" && { echo "done"; break; }
  grep -q -- "- \[ \]" "$DIR/FEATURES.md" || { echo "backlog empty"; break; }
  echo "=== Ralph iteration $i/$MAX ==="
  claude -p "Follow the instructions provided on stdin exactly." < "$DIR/PROMPT.md" \
    --model "$MODEL" --output-format json --max-turns 40 --permission-mode acceptEdits \
    --allowedTools "Read,Edit,Write,Glob,Grep,Bash(uv run pytest*),Bash(git add*),Bash(git commit*),Bash(git status*),Bash(git diff*)" \
    --disallowedTools "Edit(tests/test_game.py),Edit(tests/test_harness.py),Write(tests/test_game.py)" \
    > "runs/ralph-$i.json"
  python -c "import json;d=json.load(open('runs/ralph-$i.json'));print(d.get('result'));print('turns',d.get('num_turns'),'cost',d.get('total_cost_usd'))"
  uv run pytest -q || { echo "tests red; stopping for review"; break; }
done
git log --oneline -n 10
