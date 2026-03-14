# Kubernetes: Sidecar Pattern for Governed Agents

Deploy TapPass as a sidecar container alongside your agent. All LLM calls go through `localhost:9620` inside the pod.

## Architecture

```
┌── Pod ───────────────────────────────────┐
│  ┌──────────┐        ┌──────────────┐    │      ┌─────────┐
│  │  Agent   │──9620──│   TapPass    │────│─────▶│  OpenAI  │
│  │container │        │  (sidecar)   │    │      │  / LLM   │
│  └──────────┘        └──────────────┘    │      └─────────┘
└──────────────────────────────────────────┘
```

Your agent calls `http://localhost:9620/v1`. TapPass runs in the same pod as a sidecar.

## Deploy

```bash
# Create the secret
kubectl create secret generic tappass-keys \
  --from-literal=admin-key=tp_admin_... \
  --from-literal=agent-key=tp_... \
  --from-literal=openai-key=sk-...

# Apply the deployment
kubectl apply -f deployment.yaml
```

## Files

- `deployment.yaml` - Agent + TapPass sidecar deployment
- The agent container uses `OPENAI_BASE_URL=http://localhost:9620/v1`
- TapPass sidecar handles governance and forwards to the real LLM
