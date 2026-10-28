# Security, privacy, and trust model

## Trust zones

The operator and reviewed repository code are trusted. Imported files, their
metadata, remote model responses, agent requests, behavioral receipts, and
external Tool endpoints are untrusted until their stage validates them.

The most important invariant is authority separation:

```text
source text -> evidence only
provider response -> draft only
Tool requirement -> inert specification
Tool binding -> executable only after explicit review
passing report -> approvable, not self-approved
approval -> publishable only for the same digest
```

## Threats covered in the MVP

- Prompt injection in sources is constrained by a data-only synthesis prompt,
  strict output schema, known-unit digest validation, and controlled code
  generation.
- Common credentials are redacted from normalized units before provider use.
- Files are bounded by size/page/unit limits to reduce accidental exhaustion.
- MCP file import is disabled by default and restricted to resolved allowlist
  roots when enabled.
- Generated provider strings are serialized as Python values; providers do not
  author executable syntax.
- External Tool requirements do not execute without reviewed bindings.
- Publication is protected against stale evaluation and release overwrite.
- Streamable HTTP defaults to Contexture's loopback-safe configuration.

## Residual risks

Redaction is pattern based and cannot find every secret or personal datum. PDF
parsing and other dependencies can contain vulnerabilities. A valid citation
does not make a claim true, and a human name in an approval file is not a
cryptographic identity. Local filesystem users can alter an unpublished
workspace. The MVP has no tenant isolation, encryption-at-rest, malware scan,
signed receipt, sandbox for future custom Tools, or policy engine.

Accordingly, use non-sensitive material for early trials, keep workspaces on
appropriately protected storage, inspect remote-provider policies, and do not
expose MCP beyond loopback without authentication and origin/host controls.

## Deployment checklist

1. Set restrictive workspace permissions and backups/retention policy.
2. Confirm authorization and licenses for each imported source.
3. Review redaction counts and normalized material before remote synthesis.
4. Keep API keys in a secret manager or process environment, never arguments or
   source files.
5. Set minimal `EXPERTCOMPOSE_IMPORT_ROOTS` for MCP.
6. Keep HTTP on loopback for the MVP; if extending it, configure Contexture
   authentication, principals, allowed hosts, and allowed origins.
7. Review Tool schemas and least privilege before implementing new bindings.
8. Require behavioral receipts and domain approval for consequential use.
9. Preserve build, report, approval, and release manifests for audit.

## Data lifecycle

Raw bytes and normalized evidence are retained locally until the operator
deletes the workspace. Deletion and legal-hold workflows are not yet provided.
Do not manually remove only a catalog row: JSON artifacts and SQLite indexes
must be reconciled together. A production retention API is a Phase 2 item.
