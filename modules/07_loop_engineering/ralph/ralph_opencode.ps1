# [v2] Ralph loop on OpenCode + any model (local Ollama / llama.cpp / DGX). Same pattern as ralph.ps1 (Claude).
#   pwsh modules/07_loop_engineering/ralph/ralph_opencode.ps1 -MaxIters 3 -Model ollama/qwen3.5:9b
#   pwsh modules/07_loop_engineering/ralph/ralph_opencode.ps1 -Model dgx/google/gemma-4-26b-it
# Permissions come from .opencode/agents/ralph.md (edit allowed except protected tests; bash = pytest + git add/commit only).
# SAFETY: branch 'ralph'. Review: git log --oneline ralph ; git diff main..ralph
param([int]$MaxIters = 3, [string]$Model = "ollama/qwen3.5:9b")
$ErrorActionPreference = "Continue"
Set-Location (git rev-parse --show-toplevel)
$dir = "modules/07_loop_engineering/ralph"
if (git branch --list ralph) { git switch ralph } else { git switch -c ralph }
New-Item -ItemType Directory -Force runs | Out-Null

for ($i = 1; $i -le $MaxIters; $i++) {
    if (Select-String -Path "$dir/NOTES.md" -Pattern "RALPH_DONE" -Quiet) { Write-Host "RALPH_DONE. Stop."; break }
    if (-not (Select-String -Path "$dir/FEATURES.md" -Pattern "- \[ \]" -Quiet)) { Write-Host "Backlog empty."; break }
    Write-Host "=== Ralph (OpenCode) iteration $i / $MaxIters  model=$Model ===" -ForegroundColor Cyan
    $t0 = Get-Date
    opencode run --agent ralph -m $Model -f "$dir/PROMPT.md" "Follow the attached PROMPT.md instructions exactly." *>&1 |
        Tee-Object -FilePath "runs/ralph-oc-$i.log"
    Write-Host ("took {0:n0}s" -f ((Get-Date) - $t0).TotalSeconds) -ForegroundColor DarkGray
    uv run pytest -q
    if ($LASTEXITCODE -ne 0) { Write-Host "Tests red after iteration $i. Stop for human review." -ForegroundColor Red; break }
}
git log --oneline -n 10
