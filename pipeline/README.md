# Pipeline Configuration

TapPass governance pipelines are configured via YAML. Each pipeline defines which steps run and how they behave.

## Presets

TapPass ships with three presets:

| Preset | Use case |
|--------|----------|
| `starter` | Development, internal tools |
| `standard` | Production workloads |
| `regulated` | Financial services, healthcare, government |

```bash
# Apply a preset
tappass init --preset regulated
```

## Custom pipeline

Create a `tappass-pipeline.yaml` and import it:

```bash
tappass pipelines import tappass-pipeline.yaml
```

## Auto-generate from code scan

TapPass can scan your codebase and generate a recommended pipeline:

```bash
tappass assess --output pipeline
# generates tappass-pipeline.yaml based on what it finds
```

## Files

- `starter.yaml` - Minimal governance for development
- `standard.yaml` - Production-ready governance
- `regulated.yaml` - Full compliance (EU AI Act, GDPR, NIS2)
