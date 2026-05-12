# LangChain: ReAct Agent with Governance

TapPass governs both the LLM calls and tool executions in a LangChain agent.

## Setup

```bash
pip install tappass langchain langchain-openai
tappass quickstart
```

## Run

```bash
export TAPPASS_URL=http://localhost:9620
export TAPPASS_API_KEY=tp_...
python agent.py
```
