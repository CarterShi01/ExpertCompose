# ExpertCompose architecture and product design

Status: MVP v0.1 authoritative design; production decoupling direction active
Last updated: 2026-10-28

The authoritative boundary for Contexture, ExpertCompose, and one-creator is
[three-product-direction.md](three-product-direction.md). Its implementation
architecture is specified in
[three-product-decoupling-design.md](three-product-decoupling-design.md). These
documents preserve the v0.1 evidence/compiler/release contract defined here.

## 1. Product thesis

Agents repeatedly solve similar work but usually retain only transcripts or
unstructured memories. ExpertCompose turns heterogeneous experience and
literature into a governed, reusable expert system. The transformation is:

```text
books / papers / sessions / notes
              |
       normalize + provenance
              |
 evidence -> claims -> procedures -> tasks
              |
       Expert Blueprint (draft)
              |
      generate + evaluate + approve
              |
 ExpertNet release: Role / Skill / Tool graph
```

An ExpertNet is a structured capability map, not a generic vector collection,
single prompt, autonomous agent, or transcript summary. Roles partition
responsibility, Skills teach model-performed procedures, and Tools expose
deterministic executable capabilities. Evidence remains addressable beneath
all three.

## 2. Goals and non-goals

The MVP must accept common local source types; retain exact provenance; create
a typed, reviewable intermediate representation; produce a standalone
Contexture application; make structural and behavioral evaluation possible;
and prohibit publication without an exact passing evaluation and explicit
approval. It must work offline end to end.

The MVP does not crawl arbitrary websites, bypass source rights, train a model,
operate a vector database, execute generated Python, prove factual truth, or
run an agent loop. It does not automatically bind arbitrary external MCP
servers. Those are deliberate trust boundaries, not missing glue.

## 3. Architectural boundaries

ExpertCompose owns the compiler and product lifecycle:

1. **Source plane** — consent metadata, immutable raw bytes, normalization,
   redaction, and locators.
2. **Knowledge plane** — evidence, claims, procedures, tasks, and conflicts.
3. **Expert plane** — Role/Skill/Tool requirements in a versioned Blueprint.
4. **Artifact plane** — deterministic generated projects and build manifests.
5. **Assurance plane** — static gates, Host receipts, approval, and releases.
6. **Interface plane** — service facade, CLI, and MCP operations.

The post-MVP product adds a seventh, explicitly separate plane:

7. **Meta-organization plane** — versioned policies for team responsibility
   design, routing, decomposition, topology, coordination, verification,
   attribution, and governed evolution. It manages ExpertNets; it does not
   contain domain knowledge or replace the compiler pipeline.

Contexture owns the target runtime's immutable graph, canonical addressing,
progressive disclosure, typed Tool binding, Host-neutral invocation, and MCP
serving. It is intentionally not used as a database, model client, scheduler,
or workflow engine.

This separation lets future targets consume the same Blueprint without making
Python implementation details the product contract.

The layering was cross-checked against the local one-creator `oc_app` Team
module. ExpertCompose preserves its important split between pure domain
decisions, application use cases and ports, storage/provider adapters, typed
API projection, and Contexture-native capabilities. The MVP keeps these layers
as focused top-level modules because it has one bounded context; the exact
mapping and scale-up rule are recorded in
[one-creator-team-reference.md](one-creator-team-reference.md).

## 4. Data model

All persisted product records are strict Pydantic values with unknown fields
rejected. JSON/JSONL is the reviewable source of truth; SQLite is an index and
transactional uniqueness layer.

### Source records and normalized units

`SourceRecord` binds a content digest to project, source kind, original path,
media type, byte count, authorization statement, license label, timestamp, and
normalization metadata. A project deduplicates identical source bytes.

`NormalizedUnit` is the only content handed to synthesis. It has a source ID,
line/page/message/chunk locator, bounded redacted text, unit digest, and
redaction count. Raw files are preserved separately so normalization remains
auditable. The current limits are 50 MiB per file, 5,000 PDF pages, and 6,000
characters per unit.

### Evidence and knowledge IR

`Evidence` selects a short source excerpt and summary with kind, confidence,
tags, and exact source locator. `Claim`, `Procedure`, and `TaskSpec` reference
evidence IDs rather than copying unverifiable assertions. Unknown references
are rejected during provider-draft conversion and evaluation.

The design records confidence but does not treat it as calibrated probability.
Conflicts can be retained rather than silently resolved.

### Expert Blueprint

`ExpertBlueprint` contains one or more Role roots, Skills, Tool requirements,
Tool bindings, tasks, source IDs, knowledge records, provider identity,
version, and workflow status. It is independent of Contexture imports.

- A **Role** owns a responsibility boundary and routing instructions.
- A **Skill** is a reusable procedure performed by the host model.
- A **Tool requirement** describes deterministic capability needed by a Role;
  it is not executable code.
- A **Tool binding** explicitly maps a reviewed requirement to a built-in,
  Python, or MCP implementation and pins its input-schema digest.

The MVP automatically binds only `lookup-evidence`, a framework-owned,
read-only capability. Other required Tools block release until a future
reviewed binding flow is implemented.

### Artifact and assurance records

A build manifest pins generator version, Blueprint digest, package name, file
list, artifact digest, and unbound required Tools. Evaluation reports pin the
Blueprint digest and every check. Approval pins a passing report and named
reviewer. Release manifests pin all of those plus a copied immutable artifact.

Workflow state and timestamps are excluded from the semantic Blueprint digest;
all substantive expert content, provenance references, provider identity, and
binding details remain included.

## 5. Ingestion design

Only paths explicitly supplied by a user are imported. The CLI has the same
OS access as its caller. MCP import adds a second boundary:
`EXPERTCOMPOSE_IMPORT_ROOTS` must contain one or more resolved roots, and the
requested regular file must be within one of them. An empty allowlist disables
MCP import.

Text and Markdown require UTF-8. PDFs are parsed without executing embedded
content. JSON/JSONL traverses common `messages`, `conversation`, `turns`,
`session`, `sessions`, and `data` containers and accepts common text-part
shapes. The format is deliberately permissive at the edge and strict after
normalization.

Credential redaction covers private-key blocks, bearer tokens, common GitHub,
OpenAI-like and Slack token shapes, and named secret/password assignments.
This is defense in depth, not a data-loss-prevention guarantee. Operators must
review sources before using a remote provider.

## 6. Synthesis design

Synthesis providers implement one narrow protocol: project metadata plus
immutable sources and normalized units in, `CompositionDraft` out. Drafts are
strictly validated and cannot contain code.

The offline heuristic provider provides deterministic product operation and a
conservative baseline. It samples units across sources, makes evidence records,
creates claims, a grounded procedure, held-out task definitions, a shallow
analysis/quality Role tree, and the evidence lookup requirement. Its lower
confidence makes its limitation visible.

The OpenAI-compatible provider sends bounded redacted units and the exact
output JSON Schema. Its system contract says source content is untrusted data,
requires every artifact to cite evidence keys, prohibits invented unit
digests, distinguishes Role/Skill/Tool, and asks for a shallow tree. Returned
unit digests are checked against the input before conversion.

Provider output is always a draft. The provider cannot approve, publish, bind
an arbitrary Tool, choose filesystem paths, or execute generated content.

## 7. Deterministic generation

Generation walks the Blueprint and emits source text from controlled templates.
Model-authored strings become constructor values; they never become source-code
structure. Generated class names and package identifiers are normalized by the
generator, while Contexture validates member uniqueness and the complete lazy
graph at compilation.

Each standalone project contains:

- package metadata and a dedicated runner;
- a lazy Contexture application declaration;
- generated Role and Skill classes;
- the framework-owned `EvidenceLookup` Tool;
- bounded evidence JSON;
- the exact Blueprint and build manifest;
- artifact-specific usage documentation.

Every generated file except the manifest participates in a stable tree digest.
Rebuilding an unchanged Blueprint overwrites the same build directory with
the same semantic contents. Publication copies the build to a new immutable
release path and refuses to overwrite an existing release.

## 8. Evaluation and governance

Evaluation is performed against an exact Blueprint digest and generated build.
The release gates are:

1. all authored references resolve to persisted evidence;
2. selected sources are represented or reported as a coverage warning;
3. the Role tree stays within depth/breadth limits and has no empty leaves;
4. every required Tool has a reviewed binding;
5. the generated package imports and compiles through Contexture;
6. optional or required held-out behavioral receipts match every task case.

Behavioral execution belongs to the chosen Host and agent, not to Contexture or
the compiler. ExpertCompose exports a neutral suite and accepts observations
containing case result, opened/invoked refs, evidence refs, metrics, and notes.
CI can require these receipts even though local preview permits skipping them.

Approval is a distinct accountable action. It is allowed only after a passing
report covers the same semantic digest. Publication rechecks approval, report,
build identity, and Tool bindings. This prevents “evaluate A, edit B, publish
B” and prevents model output from self-approving.

## 9. Interfaces

`ExpertComposeService` is the stable application facade and is used by both
CLI and MCP; neither interface reimplements domain logic.

The CLI exposes initialization, project operations, ingest, compose, build,
suite export, evaluate, approve, publish, ScopeBinding, local Runtime, MCP, and
the deployment API. It emits JSON on stdout and concise errors on stderr.

The MCP application exposes the same lifecycle as a Contexture Role with a
source-safety Skill and typed Tools. Model-assisted provider credentials are
intentionally absent from MCP v0.1; a deployment-specific provider policy can
be added without putting secrets in Tool arguments.

The authenticated `/v1` HTTP boundary gives deployed consumers verified,
Scope-selected release catalogs without exposing Workspace paths. It is small
by design; the full authoring lifecycle stays on CLI/MCP until durable remote
jobs exist.

The MCP surface is a local **control plane**, not the final consumer
connector. The product direction separates a read-mostly Runtime endpoint from
the Studio/control endpoint, adds host adapter Skills, and keeps large expert
libraries behind Contexture progressive disclosure. The complete scenario
research, unified interaction flow, and precise MetaSkill Kernel definition
are specified in
[product-research-and-metaskill-kernel.md](product-research-and-metaskill-kernel.md).

## 10. Failure, recovery, and concurrency

Filesystem writes use a temporary file, `fsync`, and atomic replace. SQLite
transactions provide unique versions and catalog integrity. Raw import files
and review artifacts remain inspectable after a later stage fails. A failed
compose does not create a Blueprint; a failed generation does not publish; a
failed evaluation cannot be approved.

The MVP is safe for ordinary single-process local use and a single-writer
container deployment. SQLite arbitrates basic concurrent writes, but
multi-worker version allocation and artifact generation need an explicit lock
before horizontal scale-out. Remote object storage, distributed queues, tenant
isolation, encryption-at-rest, and retention policies remain later deployment
concerns.

## 11. Privacy and rights

Each source requires a non-empty authorization statement and retains a license
label. These fields make the decision reviewable but cannot verify that the
claim is true. Raw sources stay local unless the operator explicitly selects a
remote synthesis provider. Generated evidence uses bounded excerpts; operators
remain responsible for fair use, licenses, deletion requests, and jurisdiction.

No telemetry or remote call is made by the offline lifecycle. Provider URLs
and model names enter Blueprint provenance; API keys do not.

## 12. Extension points

Planned compatible extensions include OCR and richer parsers, incremental
source updates, embeddings as a retrieval optimization, conflict-resolution
workflows, reviewed external Tool registries, signed Host receipts, task
baseline comparison, ExpertNet diff/merge, non-Python targets, registry
publication, and continuous effectiveness monitoring. Runtime routing and
team evolution use the system-owned MetaSkill Kernel; source segmentation,
claim extraction, and artifact generation remain compiler capabilities rather
than being mislabeled as meta-skills. These extensions preserve the planes and
trust boundaries above.
