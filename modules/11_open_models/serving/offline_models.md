# Moving models to a restricted / offline work machine

Follow your org's software + data approval process first (AI models are software; some orgs restrict by
license or developer origin). Mechanics once approved:

## Ollama
Models live in `%USERPROFILE%\.ollama\models` (`blobs\` + `manifests\`). Change with env `OLLAMA_MODELS`.
1. Home: `ollama pull gemma4:26b`
2. Copy whole `models` folder (or just that model's manifest + referenced blobs) to work machine's `OLLAMA_MODELS` dir.
3. Work: `ollama list` -> appears. No internet needed to run.

## GGUF (llama.cpp / LM Studio / Ollama import)
Single file. Ollama import: Modelfile with `FROM ./gemma-4-26b-it-Q4_K_M.gguf` then `ollama create gemma4-local -f Modelfile`.
Note: hand-made Modelfile may lack the model's tool-call TEMPLATE -> native tools break -> use `LLM_TOOL_MODE=prompt`
or llama.cpp `--jinja`. (Great real-world demo of why prompt-mode exists.)

## DGX
Hugging Face safetensors dir (`huggingface-cli download <repo> --local-dir ...` where allowed), transfer, then
`vllm serve /path/to/dir ...`. Set `HF_HUB_OFFLINE=1` so vLLM never tries the network.

## Python deps offline
Home: `uv export --format requirements-txt > requirements.txt` then `pip download -r requirements.txt -d wheels/`.
Work: `uv pip install --no-index --find-links wheels/ -r requirements.txt`.
