# CrewAI: Multi-Agent Crew with Governance

TapPass governs all LLM calls and tool executions across an entire CrewAI crew. Every agent in the crew runs through the governance pipeline.

## Setup

```bash
pip install tappass crewai crewai-tools
tappass quickstart
```

## Run

```bash
export TAPPASS_API_KEY=tp_...
python main.py
```

## How it works

1. `tp_agent.configure_environment()` sets `OPENAI_BASE_URL` so CrewAI auto-routes through TapPass
2. `tp_agent.govern([tools])` wraps tool executions with governance and audit logging
3. Every LLM call from every crew agent goes through the pipeline
4. Every tool execution is logged to the audit trail
