# Docker: TapPass + Your Agent

Run TapPass alongside your agent in Docker Compose. All LLM calls from your agent route through the TapPass container.

## Quick start

```bash
docker compose up
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────┐
│   Your Agent    │────▶│    TapPass       │────▶│  OpenAI  │
│  (any framework)│     │  (governance)    │     │  / LLM   │
└─────────────────┘     └─────────────────┘     └─────────┘
       :8000                   :9620
```

Your agent calls TapPass at `http://tappass:9620/v1` (Docker network name). TapPass scans, classifies, and forwards to the LLM.

## Files

- `docker-compose.yml` - TapPass + example agent
- `agent/` - Example FastAPI agent that uses TapPass

## Configuration

Set your real OpenAI key in the environment or `.env` file:

```bash
# .env
OPENAI_API_KEY=sk-...
TAPPASS_ADMIN_KEY=tp_admin_...
```

## View audit trail

```bash
# From host
docker compose exec tappass tappass logs

# Or open dashboard
open http://localhost:9620/app
```
