# [v2] llama.cpp server: most control, most reliable Gemma 4 tool calls (chat template via --jinja).
# Get llama.cpp: winget install llama.cpp   (or GitHub release zip w/ CUDA build)
# Get a GGUF (Q4_K_M or better): download at home / from approved mirror, copy to work machine.
# Then .env:  LLM_PROFILE=llamacpp
param([string]$Model = "C:\models\gemma-4-26b-it-Q4_K_M.gguf", [int]$Ctx = 32768)
llama-server -m $Model --jinja -c $Ctx -ngl 99 --port 8080 --host 127.0.0.1
# --jinja : use model's own chat template (REQUIRED for proper tool calling)
# -ngl 99 : offload all layers to GPU.  -c : context length (agents need 16k-64k)
