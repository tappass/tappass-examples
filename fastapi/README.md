# FastAPI: Microservice with Governance

A production-ready FastAPI service where every LLM call goes through TapPass governance. Policy violations return structured 403 responses.

## Setup

```bash
pip install tappass fastapi uvicorn
tappass quickstart
```

## Run

```bash
export TAPPASS_API_KEY=tp_...
uvicorn main:app --port 8000
```

## Test

```bash
# Normal request
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Our Q3 revenue was strong.", "question": "Summarize this."}'

# Request with PII (will be redacted or blocked by TapPass)
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Send an email to jane.doe@example.com about her account balance of 42000 EUR.", "question": "Summarize."}'
```
