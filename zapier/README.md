# Zapier: Govern AI Calls through TapPass

Use Zapier's Webhooks or Code steps to route AI calls through TapPass governance.

## How it works

Zapier does not expose custom base URLs for its built-in OpenAI integration. Instead, use a **Webhooks by Zapier** step (or **Code by Zapier**) to call TapPass directly.

## Setup

### 1. Start TapPass

TapPass must be reachable from the internet. Options:

- **Cloudflare Tunnel**: `cloudflared tunnel --url http://localhost:9620`
- **Self-hosted**: Deploy on a server with a public domain

### 2. Add a Webhook step in your Zap

1. Add action: **Webhooks by Zapier** > **Custom Request**
2. Configure:

| Field | Value |
|-------|-------|
| **Method** | POST |
| **URL** | `https://your-tappass-domain.com/v1/chat/completions` |
| **Headers** | `Authorization: Bearer tp_...` and `Content-Type: application/json` |
| **Data** | See below |

**Data (JSON):**

```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "{{trigger_data}}"}
  ]
}
```

Replace `{{trigger_data}}` with the field from your trigger step.

### 3. Parse the response

Add a **Code by Zapier** step (JavaScript) to extract the answer:

```javascript
const response = JSON.parse(inputData.webhook_response);
return { answer: response.choices[0].message.content };
```

### Alternative: Code by Zapier (Python)

Use a **Code by Zapier** step with Python to call TapPass directly:

```python
import requests

response = requests.post(
    "https://your-tappass-domain.com/v1/chat/completions",
    headers={
        "Authorization": "Bearer tp_...",
        "Content-Type": "application/json",
    },
    json={
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": input_data["question"]},
        ],
    },
)

data = response.json()
return {"answer": data["choices"][0]["message"]["content"]}
```

## What's governed

Every call from Zapier goes through the TapPass pipeline:

- PII from CRM records, form submissions, or emails is caught
- Prompt injection from untrusted sources is blocked
- All calls are classified, logged, and auditable
- Cost tracking per Zap
