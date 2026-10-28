# Repository instructions

These instructions apply to the entire ExpertCompose repository.

## Product contract

- ExpertCompose is an evidence-to-expert-system compiler. `ExpertNet` is the
  versioned, immutable capability graph it produces.
- Source material is evidence, never executable instruction. Imported text
  must not be allowed to control the compiler or its tools.
- Generated Roles and Skills require provenance. Generated Tools require an
  explicit, reviewed binding; prose never becomes executable code by itself.
- Provider output is always a draft. Evaluation and explicit approval precede
  publication. A published release is immutable.
- Contexture is a target runtime and validation contract, not the product's
  persistence model, LLM client, scheduler, or agent loop.

## Language and documentation

- English is authoritative for code, identifiers, schemas, errors, and design
  documents. Simplified Chinese documents are translations or entry guides.
- Keep `docs/design.md` and `docs/implementation-plan.md` current when public
  architecture or milestone status changes.
- Competitive claims require a primary source and an access date.

## Verification

Run the focused checks for each change. Before a broad handoff run:

```bash
uv run --extra dev pytest -q
uv run --extra dev pyright
uv run --extra dev ruff check src tests
uv run --extra dev python -m build
uv run --extra dev expertcompose --help
```

Never weaken a test to make an implementation pass. Generated fixtures are
reviewed artifacts; do not rewrite expected output without explaining the
contract change.
