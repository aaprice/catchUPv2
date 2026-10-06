#!/usr/bin/env bash
# [v2] Serve an open model on the DGX as an OpenAI-compatible API ("your own Claude API" for the team).
# Run on DGX (inside your org-approved container/env). Then in .env:  LLM_PROFILE=dgx-vllm  DGX_URL=http://<dgx>:8000/v1
# Check exact Hugging Face repo ids before use (they change; Google ships Gemma 4 under several names).
set -euo pipefail
MODEL=${MODEL:-google/gemma-4-26b-it}          # e.g. google/gemma-4-31b-it, openai/gpt-oss-120b, Qwen/Qwen3-32B
PARSER=${PARSER:-gemma4}                        # gemma4 | openai (gpt-oss) | hermes (qwen) | llama3_json | mistral
vllm serve "$MODEL" \
  --host 0.0.0.0 --port 8000 \
  --max-model-len 65536 \
  --enable-auto-tool-choice --tool-call-parser "$PARSER" \
  --gpu-memory-utilization 0.85
# Multi-GPU: add --tensor-parallel-size <n_gpus>. Many parallel agents (M08) = where vLLM beats Ollama hugely.
