# Zero-Code Governance via Environment Variables

Govern any OpenAI or Anthropic-compatible tool without changing a single line of code. Set two environment variables and all calls route through TapPass.

## OpenAI-compatible tools

Works with: VS Code Copilot, Cursor, Continue, Cline, CrewAI, LangChain, LlamaIndex, Autogen, any OpenAI SDK user.

```bash
export OPENAI_BASE_URL=http://localhost:9620/v1
export OPENAI_API_KEY=tp_...
```

Then use your tools normally. Every call routes through TapPass.

## Anthropic-compatible tools

Works with: Claude Code, Cline (Anthropic mode), Anthropic SDK users.

```bash
export ANTHROPIC_BASE_URL=http://localhost:9620
export ANTHROPIC_API_KEY=tp_...
```

## Shell aliases

Add to `~/.zshrc` or `~/.bashrc`:

```bash
# Governed Claude Code
alias gclaude='ANTHROPIC_BASE_URL=http://localhost:9620 ANTHROPIC_API_KEY=tp_... claude'

# Governed Python
alias gpython='OPENAI_BASE_URL=http://localhost:9620/v1 OPENAI_API_KEY=tp_... python'
```

## Per-project .env

Create `.env` in your project root:

```env
OPENAI_BASE_URL=http://localhost:9620/v1
OPENAI_API_KEY=tp_...
```

Most frameworks (CrewAI, LangChain, dotenv-based apps) auto-load `.env` files.

## Docker / Kubernetes

```yaml
# docker-compose.yml
services:
  my-agent:
    image: my-agent:latest
    environment:
      OPENAI_BASE_URL: http://tappass:9620/v1
      OPENAI_API_KEY: tp_...
```

```yaml
# Kubernetes deployment
env:
  - name: OPENAI_BASE_URL
    value: http://tappass.tappass.svc.cluster.local:9620/v1
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: tappass-agent-key
        key: api-key
```
