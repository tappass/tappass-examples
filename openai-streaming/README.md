# OpenAI SDK: Streaming with Governance

Streaming works identically through TapPass. The governance pipeline runs on the full request before streaming begins, then tokens flow through as they are generated.

## Run

```bash
pip install openai tappass
export TAPPASS_API_KEY=tp_...
python main.py
```
