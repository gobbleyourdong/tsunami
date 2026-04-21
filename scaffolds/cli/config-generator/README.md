# cli/config-generator

**Pitch:** renders config files (YAML / JSON / TOML / ini / dotenv) from a
Jinja2 template + parameter sources, then validates the rendered output
in its target format. Lineage: `consul-template`, `envsubst`, `jinja2 CLI`,
`gomplate` — but built so missing-param failures are loud (StrictUndefined)
and the output is always parsed before being written.

## Quick start

```bash
pip install -e .

# Render a bundled template with a params file
config-generator app.yaml.j2 --params data/sample_params.yaml --format yaml

# Override individual values on the CLI
config-generator app.yaml.j2 \
  --params data/sample_params.yaml \
  --set app.env=staging --set server.port=9090 \
  --format yaml -o app.yaml

# Pull values from env vars (stripping CFG_ prefix)
CFG_APP_NAME=orbit CFG_DATABASE_URL=postgres://… \
  config-generator dotenv.env.j2 --env-prefix CFG_ --format env
```

## Parameter sources (later overrides earlier)

1. `--params file.{yaml,json,toml}` — bulk parameter source
2. `--env-prefix PFX_` — pulls `PFX_KEY=val` → `{key: val}`
3. `--set key=value` (repeatable) — inline override. Dotted keys descend:
   `--set db.host=localhost` → `{"db": {"host": "localhost"}}`.
   Values that look like JSON (`true`, `42`, `[...]`) are parsed.

## Bundled templates

- `app.yaml.j2` — generic app config (name, server, database, features)
- `dotenv.env.j2` — `.env` file with optional feature flags

Add your own under `src/config_generator/templates/` (or pass `--template
/abs/path/to/tpl.j2`). `package-data` in `pyproject.toml` ships bundled
templates with the install.

## Output formats + validation

After rendering, the output is parsed in the target format. A template
that produces invalid YAML/JSON/TOML/ini fails with a clear error rather
than silently shipping broken config. Supported: `yaml`, `json`, `toml`,
`ini`, `env`, `text` (no validation).

## Test

`pytest tests/scaffolds/config-generator/` — exercises template loading,
param merging (file + env + --set), render with StrictUndefined,
post-render validation.

## Anchors

`consul-template`, `envsubst`, `gomplate`, `jsonnet`, `ytt`, `Jinja2 CLI`.
