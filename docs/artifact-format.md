# Workspace and artifact format

```text
WORKSPACE/
  catalog.db
  projects/PROJECT/
    project.json
    sources/
      raw/SOURCE.ext
      records/SOURCE.json
      normalized/SOURCE.jsonl
    evidence/evidence.jsonl
    blueprints/vNNNN-BLUEPRINT.json
    evaluations/SUITE.json
    evaluations/EVALUATION.json
    approvals/BLUEPRINT.json
    builds/vNNNN-BLUEPRINT/
      pyproject.toml
      expert-blueprint.json
      build-manifest.json
      src/PACKAGE/...
    releases/
      vNNNN-RELEASE.json
      vNNNN-RELEASE/artifact/...
```

Every product JSON object carries strict fields; major records include a
`schema_version`. JSON/JSONL is reviewable state, while `catalog.db` accelerates
lookup and enforces uniqueness. Generated build manifests list all generated
files and the digest over path/content pairs. Release manifests identify the
exact Blueprint, evaluation report, artifact digest, publisher, and immutable
artifact path.

The v0.1 layout is local and forward-migratable but is not yet a frozen public
wire protocol. Consumers should use the Python models or generated manifest,
reject unknown major schema versions, and avoid depending on SQLite internals.
