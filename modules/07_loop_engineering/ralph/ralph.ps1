# Ralph loop (PowerShell). Outer loop: fresh Claude Code context each iteration; state lives in files + git.
#   pwsh modules/07_loop_engineering/ralph/ralph.ps1 -MaxIters 5 -Model sonnet
# SAFETY: runs on branch 'ralph'. Review with: git log --oneline ralph ; git diff main..ralph
param([int]$MaxIters = 5, [string]$Model = "sonnet")
$ErrorActionPreference = "Continue"
$root = (git rev-parse --show-toplevel)
Set-Location $root
$dir = "modules/07_loop_engineering/ralph"
if (git branch --list ralph) { git switch ralph } else { git switch -c ralph }
New-Item -ItemType Directory -Force runs | Out-Null

for ($i = 1; $i -le $MaxIters; $i++) {
    if (Select-String -Path "$dir/NOTES.md" -Pattern "RALPH_DONE" -Quiet) { Write-Host "RALPH_DONE found. Stopping."; break }
    if (-not (Select-String -Path "$dir/FEATURES.md" -Pattern "- \[ \]" -Quiet)) { Write-Host "Backlog empty."; break }
    Write-Host "=== Ralph iteration $i / $MaxIters ===" -ForegroundColor Cyan
    $out = Get-Content "$dir/PROMPT.md" -Raw | claude -p "Follow the instructions provided on stdin exactly." `
        --model $Model --output-format json --max-turns 40 `
        --permission-mode acceptEdits `
        --allowedTools "Read,Edit,Write,Glob,Grep,Bash(uv run pytest*),Bash(git add*),Bash(git commit*),Bash(git status*),Bash(git diff*)" `
        --disallowedTools "Edit(tests/test_game.py),Edit(tests/test_harness.py),Write(tests/test_game.py)"
    $out | Set-Content "runs/ralph-$i.json"
    $j = $out | ConvertFrom-Json
    Write-Host ("result: " + $j.result) 
    Write-Host ("turns={0} cost_estimate=`${1}" -f $j.num_turns, $j.total_cost_usd) -ForegroundColor DarkGray
    uv run pytest -q
    if ($LASTEXITCODE -ne 0) { Write-Host "Tests red after iteration $i. Stopping for human review." -ForegroundColor Red; break }
}
git log --oneline -n 10
