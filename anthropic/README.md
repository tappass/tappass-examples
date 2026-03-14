# Anthropic Claude: Governed through TapPass

TapPass has a native Anthropic Messages API gateway. Point the Anthropic SDK at TapPass and all Claude calls are governed.

## Setup

```bash
pip install anthropic tappass
tappass quickstart
```

## Run

```bash
export TAPPASS_API_KEY=tp_...
python main.py
```

## Also works with Claude Code

```bash
export ANTHROPIC_BASE_URL=http://localhost:9620
export ANTHROPIC_API_KEY=tp_...
claude
```

All Claude Code calls are now governed. No code changes needed.
