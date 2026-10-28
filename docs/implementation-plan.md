# MVP implementation plan and delivery ledger

Status: v0.1 implemented; production expansion remains planned
Last updated: 2026-10-28

## Acceptance definition

The first MVP is complete when a clean machine can import at least a document
and an agent-session export, produce a provenance-complete Blueprint without a
network dependency, generate and compile a standalone Contexture project,
evaluate it, require a named approval, publish an immutable artifact, operate
the same flow through CLI and MCP, and pass unit, integration, typing, lint,
and package-build gates. Documentation must state security and competitive
context without claiming that structural validation equals expert quality.

## Delivered work packages

### WP1 — Repository and contract

- Python package metadata, MIT license, CI matrix, contribution and security
  policies.
- English authoritative docs plus a Simplified Chinese entry guide.
- Repository instructions pinning the evidence/draft/binding/approval trust
  boundary.

### WP2 — Durable workspace

- Reviewable JSON/JSONL artifacts and a SQLite catalog.
- Atomic file replacement, transactional uniqueness, content deduplication,
  Blueprint versioning, and immutable release paths.
- Explicit project directory layout for raw sources, normalized units,
  evidence, Blueprints, evaluations, approvals, builds, and releases.

### WP3 — Source acquisition

- Text, Markdown, PDF, JSON, JSONL, and agent-session normalization.
- Size, page, and unit bounds; UTF-8 checks; exact locators.
- Consent/license metadata, content digests, redaction, and MCP path allowlist.

### WP4 — Compiler IR and synthesis

- Strict records for evidence, claims, procedures, tasks, Roles, Skills, Tool
  requirements and bindings.
- Referential validation and semantic digests.
- Deterministic offline provider and bounded OpenAI-compatible provider.
- Prompt-injection boundary: sources are data and output is schema-only draft.

### WP5 — Contexture target

- Deterministic standalone project generator.
- Lazy Role/Skill graph, real read-only evidence Tool, exact bundled evidence,
  dedicated runner, Blueprint and build manifest.
- Compilation performed through Contexture as a release gate.

### WP6 — Evaluation and governance

- Provenance, coverage, graph-shape, Tool-binding and compilation checks.
- Held-out suite export and neutral Host observation schema.
- Digest-pinned reports, named approval, publication revalidation, and
  overwrite-resistant immutable releases.

### WP7 — Product interfaces

- One application service facade.
- JSON CLI for every lifecycle stage.
- Native Contexture MCP control Role with typed Tools and source-safety Skill.

### WP8 — Verification and examples

- Model, ingestion, workspace, synthesis, generator, evaluation, governance,
  MCP and CLI tests.
- End-to-end offline example and CI on supported Python versions.
- Pyright strict mode, Ruff, wheel/sdist build, and CLI smoke gate.

## Verification matrix

| Requirement | Evidence |
|---|---|
| Source bytes deduplicate | workspace/ingestion tests |
| Secrets stay out of normalized prompts | redaction tests |
| Provider cannot invent source units | synthesis rejection test |
| Same semantic input has a stable digest | model/end-to-end test |
| Generated project is executable structure | Contexture compile test |
| Unbound required Tools block | evaluation/governance tests |
| Missing Host receipts can be required | evaluation tests |
| Failed or stale evaluation cannot approve | governance tests |
| Publish cannot overwrite a release | end-to-end test |
| MCP import stays within allowlist | MCP Tool tests |
| Distribution is installable | package build gate |

## Post-MVP phases

The product sequence and MetaSkill Kernel are defined in detail in
[product-research-and-metaskill-kernel.md](product-research-and-metaskill-kernel.md).
In particular, “meta-skill” means organization-level control of the expert
team—responsibilities, roster, routing, topology, coordination, verification,
attribution, and evolution—not the prompts used by ingestion or synthesis
pipeline stages.

### Phase 2 — Production ingestion and editorial workflow

Add EPUB/HTML/DOCX/OCR adapters, URL acquisition with robots/rights metadata,
incremental source revisions, deletions and retention, evidence editing,
conflict queues, and a reviewer UI. Introduce project-level file locks and
object-storage abstractions before multi-worker deployment.

Exit gate: corpus update produces a clear diff, affected expert nodes are
identified, and old releases remain reproducible.

### Phase 3 — Quality science

Add task-dataset import, generated/adversarial test proposals, baseline agents,
paired comparisons with and without ExpertNet, rubric calibration, cost and
latency metrics, signed Host receipts, regression thresholds, and failure-case
attribution back to evidence/Role/Skill.

Exit gate: publication policy can require statistically meaningful improvement
on a versioned held-out set, not merely structural validity.

### Phase 4 — Tool registry and deployment

Add reviewed Python/MCP binding manifests, capability/schema compatibility,
credential references, sandbox policy, principal-aware authorization, registry
signing, remote artifact storage, deprecation, and rollback.

Exit gate: external executable capability never enters a release without
reviewed identity, schema digest, least privilege, integration tests, and
deployment approval.

### Phase 5 — ExpertNet ecosystem

Add graph diff/merge, reusable subnets, organization policy packs, TypeScript
and Go target generators, marketplace metadata, dependency resolution,
continuous evaluation, and feedback-to-draft proposals.

Exit gate: components remain provenance-complete and version-resolvable across
language targets and organizations.

### Phase 6 — Runtime connector and MetaSkill Kernel

Split the current local control MCP into a least-privilege Runtime plane and a
Studio/control plane. Add remote OAuth, tenant-aware authorization, host
adapter Skills, Expert Registry releases, explicit versioned run handles,
outcome/trace records, and compact expert/version/evidence disclosure.

Implement the MetaSkill Kernel in three bounded loops:

- build-time responsibility architecture, topology design, and roster
  ablation;
- run-time expert routing, task decomposition, coordination, communication,
  verification, and stopping;
- learning-time fault/contribution attribution, candidate evolution,
  held-out evaluation, approval, canary, and rollback.

Exit gate: a user connects one Runtime endpoint, asks a normal task in two
different hosts, receives the same pinned ExpertNet behavior with traceable
evidence, and cannot access Studio authority. No organization change can reach
the release channel without independent held-out evidence and approval.

## Risks and mitigations

- **Confident but wrong synthesis:** evidence refs, explicit uncertainty,
  domain approval, and behavioral comparison.
- **Prompt injection in sources:** data-only contract, strict schema, digest
  checks, no generated-code execution.
- **Copyright/privacy leakage:** authorization records, local default, bounded
  excerpts, redaction, provider disclosure, retention work in Phase 2.
- **Role-tree overproduction:** depth/breadth gates and held-out navigation
  metrics.
- **Tool escalation:** requirements are inert until reviewed binding; MCP file
  import is allowlisted.
- **Evaluation gaming:** held-out cases, neutral receipts, baseline comparison,
  and later signed runners.
- **Framework coupling:** target-independent Blueprint and generated-target
  boundary.

## Release procedure

Run the complete development gate, inspect generated example artifacts, review
the semantic diff and competitive claims, update the changelog, tag the exact
commit, build from the tag, and publish checksums. Do not publish a generated
ExpertNet unless its own evaluation and approval chain is complete.
