# ExpertCompose

ExpertCompose compiles books, papers, agent-session exports, and operational
notes into source-grounded expert systems that other agents can navigate and
use. Its core artifact is an **ExpertNet**: a versioned Role/Skill/Tool graph
with evidence provenance, evaluation receipts, human approval, and an
immutable release.

The first MVP is a local-first Python product built on Contexture. Contexture
provides the lazy, addressable runtime graph and MCP surface; ExpertCompose
owns ingestion, synthesis, provenance, persistence, evaluation, governance,
and project generation.

## What works in v0.1

- Import UTF-8 text, Markdown, PDF, JSON, JSONL, and common agent-session
  shapes. Raw bytes are preserved; model-facing units are bounded and common
  credentials are redacted.
- Compose a deterministic offline ExpertNet, or use an explicitly configured
  OpenAI-compatible synthesis provider.
- Persist strict, reviewable intermediate representations for sources,
  evidence, claims, procedures, tasks, Roles, Skills, and Tool requirements.
- Generate a standalone Contexture project with a real evidence-search Tool.
- Evaluate provenance, source coverage, tree shape, Tool bindings, generated
  application compilation, and optional held-out Host receipts.
- Require a passing evaluation and named approval before immutable local
  publication.
- Operate the lifecycle from the CLI or through a native Contexture MCP server.

ExpertCompose does not execute instructions found in imported content, silently
turn model output into code, or claim that structural checks prove domain
correctness. See [the design](docs/design.md) and [security model](docs/security.md).

## Quick start

```bash
uv sync --extra dev
uv run expertcompose --workspace .demo init
uv run expertcompose --workspace .demo project create research-review \
  --title "Research Review" \
  --objective "Answer questions from the supplied literature with traceable evidence"
uv run expertcompose --workspace .demo ingest research-review examples/sources/review.md \
  --authorization "I own this example and authorize local processing"
uv run expertcompose --workspace .demo compose research-review
uv run expertcompose --workspace .demo build research-review
uv run expertcompose --workspace .demo evaluate research-review
uv run expertcompose --workspace .demo approve research-review --approved-by local-reviewer
uv run expertcompose --workspace .demo publish research-review --published-by local-reviewer
```

The offline heuristic provider makes this flow reproducible without an API
key. It is a transparent baseline, not a substitute for domain review. To use
an OpenAI-compatible endpoint:

```bash
export EXPERTCOMPOSE_API_KEY='...'
uv run expertcompose --workspace .demo compose research-review \
  --provider openai --model your-model --base-url https://provider.example/v1
```

Secrets are read from the named environment variable and are not stored in the
workspace. Source material sent to a remote provider remains subject to that
provider's data policy.

## MCP control plane

Local file import over MCP is disabled until an operator sets an explicit
allowlist:

```bash
export EXPERTCOMPOSE_WORKSPACE="$PWD/.demo"
export EXPERTCOMPOSE_IMPORT_ROOTS="$PWD/examples/sources"
uv run expertcompose serve
```

Use `--transport streamable-http --port 8080` for a loopback HTTP endpoint.
The MVP CLI deliberately does not expose a non-loopback bind; production
deployment must add authentication and Contexture's network-origin controls.

## Repository map

- `src/expertcompose/ingestion.py` — bounded normalization and redaction
- `src/expertcompose/models.py` — strict versioned intermediate representation
- `src/expertcompose/synthesis.py` — offline and model-assisted composition
- `src/expertcompose/generator.py` — standalone Contexture project generation
- `src/expertcompose/evaluation.py` — deterministic and behavioral gates
- `src/expertcompose/governance.py` — approval and immutable publication
- `src/expertcompose/mcp.py` — Contexture-native MCP operations
- `docs/competitive-landscape.md` — sourced open-source and market comparison
- `docs/one-creator-team-reference.md` — local Team-module design mapping
- `docs/implementation-plan.md` — delivered MVP and forward plan

## Development gate

```bash
uv run --extra dev pytest -q
uv run --extra dev pyright
uv run --extra dev ruff check src tests
uv run --extra dev python -m build
uv run --extra dev expertcompose --help
```

English documentation and code are authoritative. [README.zh-CN.md](README.zh-CN.md)
is the Simplified Chinese entry guide.

## License

MIT. Imported sources and generated artifacts retain their own rights and
obligations; the MIT license does not grant rights to third-party material.
