# CrewAI: Multi-Agent Crew with Governance

TapPass governs all LLM calls and tool executions across an entire CrewAI crew. Every agent in the crew runs through the governance pipeline.

## Setup

```bash
pip install "tappass>=0.7.0,<0.8" crewai crewai-tools
tappass quickstart
```

## Run

```bash
export TAPPASS_URL=http://localhost:9620
export TAPPASS_API_KEY=tp_...
python main.py
```

## How it works

1. Setting `OPENAI_BASE_URL=$TAPPASS_URL/v1` makes CrewAI's OpenAI client route through TapPass
2. `tappass.govern([tools], ...)` wraps tool executions with governance and audit logging
3. Every LLM call from every crew agent goes through the pipeline
4. Every tool execution is logged to the audit trail
