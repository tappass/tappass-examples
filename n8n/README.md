# n8n: Govern AI Nodes through TapPass

Govern all AI calls in your n8n workflows by pointing the OpenAI credentials at TapPass. No custom nodes needed.

## How it works

n8n's AI nodes (OpenAI Chat, AI Agent, AI Chain) use the OpenAI API under the hood. TapPass is a drop-in OpenAI-compatible gateway. Change the base URL and all calls are governed.

## Setup

### 1. Start TapPass

```bash
pip install tappass
tappass quickstart
```

Note your TapPass URL (`http://localhost:9620`) and API key (`tp_...`).

### 2. Configure n8n credentials

In n8n, go to **Credentials** and create a new **OpenAI API** credential:

| Field | Value |
|-------|-------|
| **API Key** | `tp_...` (your TapPass agent key) |
| **Base URL** | `http://localhost:9620/v1` |

If TapPass runs on a different host (e.g. Docker), use that host's address:

```
http://tappass:9620/v1          # Docker network
https://tappass.your-domain.com/v1  # Your own domain
```

### 3. Use the credential in AI nodes

Any n8n node that accepts OpenAI credentials now routes through TapPass:

- **OpenAI Chat Model** node
- **AI Agent** node
- **AI Chain** nodes (Summary, QA, etc.)
- **OpenAI** node (direct API calls)

Just select the TapPass credential you created. The workflow runs exactly as before, but every LLM call is now scanned, classified, and logged.

## Example workflow

Import `workflow.json` into n8n to get a working example:

1. Open n8n
2. Click **Import from file**
3. Select `workflow.json`
4. Update the OpenAI credential to use your TapPass URL + key

The workflow:
1. Receives a webhook with a question
2. Sends it to GPT-4o-mini through TapPass
3. Returns the governed response

## What's governed

Every LLM call from n8n goes through the TapPass pipeline:

- **PII detection**: Personal data in prompts is caught before reaching the model
- **Prompt injection**: Malicious inputs from webhooks or user data are blocked
- **Secret scanning**: API keys or passwords in workflow data are caught
- **Data classification**: Every call is classified by sensitivity level
- **Audit trail**: Full log of what was sent, what came back, and what was blocked

## Docker setup

If you run n8n and TapPass in Docker:

```yaml
# docker-compose.yml
services:
  tappass:
    image: tappass/tappass:latest
    ports:
      - "9620:9620"
    environment:
      TAPPASS_ADMIN_KEY: tp_admin_...

  n8n:
    image: n8nio/n8n
    ports:
      - "5678:5678"
    environment:
      # Optional: set as default for all OpenAI nodes
      OPENAI_BASE_URL: http://tappass:9620/v1
      OPENAI_API_KEY: tp_...
```

With the environment variables set, n8n automatically uses TapPass for all OpenAI calls without any credential configuration.

## Anthropic models in n8n

For Claude models in n8n, create an **Anthropic** credential:

| Field | Value |
|-------|-------|
| **API Key** | `tp_...` |
| **Base URL** | `http://localhost:9620` |

## Monitoring

Check what n8n is sending through TapPass:

```bash
# Tail the audit trail
tappass logs

# Or open the dashboard
open http://localhost:9620/app
```

Every n8n workflow execution that touches an AI node will appear in the TapPass audit trail with full details: prompt, response, classification, and any blocks.
