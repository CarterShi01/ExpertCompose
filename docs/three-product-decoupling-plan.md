# Three-product decoupling implementation plan

Status: active implementation ledger  
Last updated: 2026-10-29
Design: [three-product-decoupling-design.md](three-product-decoupling-design.md)
Evidence: [verification-2026-10-29.md](verification-2026-10-29.md)

## Completion definition

The program is complete only when all three repositories pass their independent
gates, OC functional tests pass against a separately started ExpertCompose
service, the legacy OC Team implementation is no longer authoritative for the
extracted behavior, and deployment/rollback instructions have been exercised.

Documentation or interface scaffolding alone does not satisfy completion.

## Workstream 0 — Baseline and contract freeze

- [x] Inspect current repository boundaries and existing selection/auth seams.
- [x] Record the minimal product direction in English and Simplified Chinese.
- [x] Capture clean baseline gates for Contexture and ExpertCompose.
- [x] Establish a reproducible OC development/test environment.
- [x] Capture focused OC Team, Authorization, Project, and Runtime test results.
- [x] Freeze Team roster, selector, assignment, Draft, and permission fixtures.
- [x] Record current generated/profile declaration digests for migration checks.

Exit gate: current behavior has executable evidence, and unrelated dirty OC
deployment changes are identified and preserved.

## Workstream 1 — ExpertCompose internal boundaries

- [ ] Add domain/application/port/adapter package boundaries without changing
  v0.1 public behavior.
- [ ] Introduce `workspace_id` APIs and deterministic compatibility for stored
  `project_id` v0.1 records.
- [ ] Extract persistence protocols from the concrete local Workspace adapter.
- [ ] Add actor authorization and audit ports with trusted-local defaults.
- [ ] Add artifact and durable-job ports; retain synchronous local execution.
- [x] Update architecture/security documentation and package exports.

Exit gate: the complete v0.1 lifecycle passes through ports with the same
semantic digests and generated artifact bytes.

## Workstream 2 — ScopeBinding and selected Runtime

- [x] Add the strict ScopeBinding model and semantic digest.
- [x] Add SQLite schema migration and idempotent repository operations.
- [x] Add create/list/get/disable use cases with optimistic concurrency.
- [x] Validate Role selectors through the exact published release graph.
- [x] Add CLI and Studio MCP operations.
- [x] Update generated runners to install the Contexture selector explicitly.
- [x] Add a Runtime host that intersects request selection with authorized
  ScopeBinding selectors.
- [x] Test exact release pinning, denial, disable, and concurrent requests.

Exit gate: personal mode serves a full release locally; a scoped host serves
only its selected Role subtree and refuses direct access outside it.

## Workstream 3 — OC ExpertNet pack and compatibility projection

- [x] Define a deterministic OC source-pack manifest using existing Blueprint
  fields and annotations.
- [x] Export Profile, Skill, Tool, and MCP declaration content without importing
  OC runtime objects into ExpertCompose.
- [x] Import the pack into an ExpertCompose Workspace with provenance.
- [x] Compose/evaluate/approve/publish the first OC ExpertNet release.
- [x] Project that release into the existing OC `ProfileDescriptor` contract.
- [x] Compare every legacy roster/selector/assignment fixture.

Exit gate: a released ExpertNet reproduces the frozen OC catalog behavior with
no ExpertCompose import of `oc_app` and no OC access to ExpertCompose storage.

## Workstream 4 — Remote management host

- [x] Specify versioned JSON schemas and error envelopes.
- [x] Add service-client authentication and request actor attribution.
- [x] Add Workspace, reviewed-pack, build/evaluate/approve/publish, release,
  catalog, and ScopeBinding endpoints.
- [ ] Add general document upload and asynchronous composition endpoints.
- [ ] Add durable job submission/status/idempotency endpoints.
- [x] Add request bounds, health, readiness, and request identifiers.
- [ ] Add PostgreSQL-compatible metadata adapter and object-store adapter.
- [ ] Add API and worker entry points from the same application code.
- [x] Build a container image and local compose deployment.

Exit gate: a clean deployment performs the complete lifecycle remotely and
survives API/worker restart without losing a job or published release.

## Workstream 5 — OC service adapter and authorization composition

- [x] Add an ExpertCompose client adapter to OC.
- [x] Implement HTTP client, timeouts, bounded retries, and explicit degraded
  responses.
- [x] Map OC caller and Project authorization to ScopeBinding access.
- [x] Replace the catalog source behind the existing Team facade.
- [x] Preserve OC Hand placement after Expert selection.
- [x] Keep OC Project Tool authorization at the operation boundary.
- [x] Add a configuration switch and executable shadow comparison.

Exit gate: OC can run with its legacy Team catalog disabled while Work,
Automation, Project, and Contexture surfaces retain required behavior.

## Workstream 6 — Stateful Team workflow migration

- [ ] Map pending Team Drafts to Blueprint drafts or finish them before cutover.
- [x] Route new capability acquisition into Workspace evidence ingestion.
- [x] Route session-learning recommendations into evidence-backed Blueprint
  revisions.
- [x] Route Skill evolution candidates through ExpertCompose evaluation and
  publication.
- [ ] Export/import active state with schema versions, digests, and idempotency.
- [ ] Perform bounded write-freeze rehearsal and rollback rehearsal.
- [ ] Remove legacy write paths after the rollback window.

Exit gate: every extracted Team change reaches an immutable release through one
ExpertCompose governance path; OC has no second authoritative writer.

## Workstream 7 — Independent verification

### Contexture

- [x] `uv run --extra dev pytest -q`
- [x] `uv run --extra dev pyright`
- [x] `uv run --extra dev ruff check contexture tests scripts`
- [x] `uv run --extra dev validate-pyproject pyproject.toml`
- [x] `uv run python scripts/verify_porting_contract.py`
- [x] `uv run python scripts/product_manifest.py --check`
- [x] `uv run python scripts/incremental_manifest.py`
- [x] `uv run python scripts/verify_porting_contract.py --release-bindings`

### ExpertCompose

- [x] `uv run --extra dev pytest -q`
- [x] `uv run --extra dev pyright`
- [x] `uv run --extra dev ruff check src tests`
- [x] `uv run --extra dev python -m build`
- [x] `uv run --extra dev expertcompose --help`
- [x] clean-wheel installation and personal CLI/MCP smoke
- [x] deployment API, selected Runtime, and external OC integration tests

### one-creator

- [x] focused Team, Authorization, Project, Work, and Runtime unit tests
- [x] static/type/lint and repository-architecture gates used by the repository
- [x] OC application functional test against an external ExpertCompose process
- [x] unauthorized-client and service-unavailable functional tests
- [x] deployment manifest and generated-artifact consistency checks

Exit gate: all evidence is captured from current commits with no skipped or
weakened tests.

## Workstream 8 — Deployment and cutover

- [ ] Publish compatible Contexture and ExpertCompose packages/images.
- [ ] Apply ExpertCompose database migration in staging.
- [ ] Deploy worker, then API/Runtime.
- [x] Import and verify the OC ExpertNet release.
- [x] Create required Project ScopeBindings.
- [x] Run shadow comparison of all 38 released and legacy Profiles.
- [x] Switch OC read authority, then reusable-team content write authority when
  the ExpertCompose service configuration is enabled.
- [x] Exercise fail-closed service loss, binding replacement recovery, and the
  configuration fallback path.
- [ ] Remove expired legacy state and compatibility code in a later release.

Exit gate: production-like deployment and rollback are both demonstrated, and
each product remains operable without the others in its documented standalone
mode.

## Change discipline

Each change contains one bounded concept or adapter and its executable evidence.
Contexture changes are made only for a missing runtime primitive proven by a
failing conformance test. ExpertCompose owns product contracts. OC changes use
its public facades and composition root; project-specific behavior does not
move downward.

The ledger is updated only after the named evidence passes. A partial green
workstream does not satisfy later exit gates.

