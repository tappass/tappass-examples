# LlamaIndex: RAG Pipeline with Governance

TapPass governs the LLM calls in your RAG pipeline. Retrieval happens locally, but every LLM interaction is scanned for PII, injection, and secrets.

## Setup

```bash
pip install tappass llama-index llama-index-llms-openai
tappass quickstart
```

## Run

```bash
export TAPPASS_API_KEY=tp_...
python main.py
```
