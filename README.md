<p align="center">
  <strong>TapPass Examples</strong><br>
  <em>Integration examples for AI agent governance</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/tappass/"><img src="https://img.shields.io/pypi/v/tappass?color=blue" alt="PyPI"></a>
  <a href="https://tappass.ai"><img src="https://img.shields.io/badge/docs-tappass.ai-blueviolet" alt="Docs"></a>
  <a href="https://github.com/tappass/tappass-examples/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License"></a>
</p>

---

Code examples showing how to integrate [TapPass](https://tappass.ai) with popular AI frameworks, no-code platforms, and deployment environments.

TapPass sits between your AI agents and the LLM. Every call is scanned for PII, prompt injection, and policy violations, then classified, logged, and audited.

## Quick start

```bash
# Install TapPass
pip install tappass

# Start the server + register your first agent
tappass quickstart
```

## Examples

### Frameworks (Python)

| Example | Framework | What it shows |
|---------|-----------|---------------|
| [`openai-basic/`](openai-basic/) | OpenAI SDK | Drop-in governance. Change `base_url`, done. |
| [`openai-streaming/`](openai-streaming/) | OpenAI SDK | Streaming responses with full governance |
| [`crewai/`](crewai/) | CrewAI | Multi-agent crew with governed tools + LLM |
| [`langchain/`](langchain/) | LangChain | ReAct agent with governed tool execution |
| [`llamaindex/`](llamaindex/) | LlamaIndex | RAG pipeline with governed LLM |
| [`pydantic-ai/`](pydantic-ai/) | Pydantic AI | Type-safe agent with governed tools |
| [`anthropic/`](anthropic/) | Anthropic SDK | Claude through TapPass governance |
| [`fastapi/`](fastapi/) | FastAPI | Microservice with governed LLM as a dependency |
| [`http-only/`](http-only/) | Any (httpx) | Raw HTTP. No SDK needed. |

### No-code platforms

| Example | Platform | What it shows |
|---------|----------|---------------|
| [`n8n/`](n8n/) | n8n | Govern AI nodes by changing the base URL |
| [`make/`](make/) | Make (Integromat) | HTTP module pointing at TapPass |
| [`zapier/`](zapier/) | Zapier | Custom API action through TapPass gateway |

### Zero-code (env vars only)

| Example | Tool | What it shows |
|---------|------|---------------|
| [`env-vars/`](env-vars/) | Any OpenAI/Anthropic tool | Set 2 env vars. No code changes. |

### DevOps

| Example | Platform | What it shows |
|---------|----------|---------------|
| [`docker/`](docker/) | Docker Compose | TapPass + your agent in containers |
| [`kubernetes/`](kubernetes/) | Kubernetes | Sidecar pattern for governed agents |

### Pipeline config

| Example | What it shows |
|---------|---------------|
| [`pipeline/`](pipeline/) | Pipeline YAML configuration and presets |

---

## How it works

```
Your Agent (any framework)
  |
  v
TapPass Gateway ── governance pipeline ──> LLM / Tool
  |
  Before               During              After
  ├─ PII detection     ├─ LLM/tool call    ├─ Output scanning
  ├─ Secret scanning   ├─ Permissions      ├─ Cost tracking
  ├─ Injection block   ├─ Human approval   └─ Audit trail
  └─ Classification    └─ Rate limiting
```

## Requirements

- Python 3.10+
- `pip install tappass`
- A running TapPass server (`tappass up`)

## Links

- [TapPass website](https://tappass.ai)
- [Documentation](https://docs.tappass.ai)
- [Python SDK on PyPI](https://pypi.org/project/tappass/)

## License

Apache 2.0. See [LICENSE](LICENSE).
