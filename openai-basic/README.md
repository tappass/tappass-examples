# OpenAI SDK: Basic Governance

The simplest integration. Change `base_url` and every OpenAI call runs through TapPass governance.

## Setup

```bash
pip install openai tappass
tappass quickstart
```

## Run

```bash
export TAPPASS_API_KEY=tp_...
python main.py
```

## What's governed

Every call goes through the TapPass pipeline:

- PII detection and redaction
- Prompt injection blocking
- Secret scanning
- Data classification
- Cost tracking
- Full audit trail

Check the audit trail: `tappass logs`
