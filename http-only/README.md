# HTTP Only: No SDK Needed

TapPass exposes an OpenAI-compatible REST API. Call it with any HTTP client. No SDK dependency.

## Run

```bash
pip install httpx
export TAPPASS_API_KEY=tp_...
python main.py
```

## cURL example

```bash
curl http://localhost:9620/v1/chat/completions \
  -H "Authorization: Bearer tp_..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "What is the EU AI Act?"}]
  }'
```

The response includes standard OpenAI fields plus a `tappass` object with governance metadata.
