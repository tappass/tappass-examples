# Make (Integromat): Govern AI Calls through TapPass

Use TapPass as the OpenAI endpoint in Make scenarios. Every AI call is governed, classified, and logged.

## How it works

Make's OpenAI modules let you set a custom API URL. Point them at TapPass and all calls go through the governance pipeline.

## Setup

### 1. Start TapPass

```bash
pip install tappass
tappass quickstart
```

TapPass must be reachable from the internet for Make (cloud-hosted). Options:

- **Cloudflare Tunnel**: `cloudflared tunnel --url http://localhost:9620`
- **ngrok**: `ngrok http 9620`
- **Self-hosted**: Deploy TapPass on a server with a public IP or domain

### 2. Configure Make connection

In your Make scenario:

1. Add an **OpenAI** module (e.g., "Create a Chat Completion")
2. Click **Create a connection**
3. Set:

| Field | Value |
|-------|-------|
| **API Key** | `tp_...` (your TapPass agent key) |
| **Custom API URL** | `https://your-tappass-domain.com/v1` |

### 3. Use the HTTP module (alternative)

If the OpenAI module does not support custom URLs in your Make plan, use the **HTTP: Make a request** module:

| Field | Value |
|-------|-------|
| **URL** | `https://your-tappass-domain.com/v1/chat/completions` |
| **Method** | POST |
| **Headers** | `Authorization: Bearer tp_...` and `Content-Type: application/json` |
| **Body** | `{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "..."}]}` |

The response is standard OpenAI format. Parse `choices[0].message.content` for the answer.

## What's governed

Every call from Make goes through the TapPass pipeline:

- PII in user inputs from forms or databases is caught
- Prompt injection from untrusted data sources is blocked
- All calls are classified and logged to the audit trail
- Cost tracking per Make scenario

## Monitoring

```bash
tappass logs          # see all calls from Make
open http://localhost:9620/app  # dashboard
```
