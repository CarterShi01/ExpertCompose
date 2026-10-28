# Three-product decoupling design

Status: implementation design  
Last updated: 2026-10-28  
Direction: [three-product-direction.md](three-product-direction.md)

## 1. Objective

Extract the reusable expert-team product behavior currently embedded in
one-creator into ExpertCompose while keeping Contexture, ExpertCompose, and
one-creator independently installable, testable, deployable, and useful.

The target is complete when:

1. Contexture has no upward dependency on ExpertCompose or OC.
2. ExpertCompose can author, evaluate, publish, bind, and serve ExpertNets in
   personal mode without OC.
3. ExpertCompose can run as an authenticated service without importing OC.
4. OC uses public ExpertCompose contracts for extracted Team behavior and
   retains its own Project and Authorization domains.
5. Each repository has an independent green gate, and OC has functional tests
   proving the composed behavior.

## 2. Architectural invariants

### 2.1 Minimal vocabulary

No new aggregate is introduced when an existing one has the same lifecycle.

| Product | Durable concepts used by this design |
|---|---|
| Contexture | Role, Skill, Tool |
| ExpertCompose | Workspace, Blueprint, ExpertNet, ScopeBinding |
| one-creator | Project, Scope, Authorization |

An ExpertNet is the team. Role paths organize that team. A separate Team,
Namespace, ExpertDefinition, Catalog, RuntimeTarget, or ChangeProposal model is
not required for this migration.

### 2.2 Dependency direction

```text
one-creator -> ExpertCompose public contract -> Contexture public contract
```

Contexture does not import either product. ExpertCompose does not import OC.
OC may use an ExpertCompose client package, generated schema, or signed release
artifact, but never ExpertCompose persistence internals.

### 2.3 Authority separation

- Contexture enforces the selected Role surface and typed invocation.
- ExpertCompose governs expert content, versions, evaluation, publication, and
  the ScopeBinding record.
- The Scope owner authorizes business access.
- The Tool owner authorizes each business operation performed by a Tool.

Selecting a Contexture surface is enforcement after an authorization decision;
it is not a replacement for the decision.

### 2.4 Published artifacts

Published ExpertNet releases are immutable and content-addressed. ScopeBinding
records point to exact release IDs. Moving a channel or publishing a later
release never silently changes an existing binding.

## 3. Current-state assessment

Contexture already supplies the required runtime primitive:

- exact Role refs and terminal direct-child patterns such as `team/*`;
- selected subtrees and promoted descendant roots;
- discover/open/invoke refusal outside the selected surface;
- request selection intersected with a principal-derived ceiling;
- transport-independent fixed selection for local hosts.

No business Scope model is required in Contexture for the initial extraction.

ExpertCompose owns evidence ingestion, strict Blueprint records, deterministic
Contexture generation, evaluation, approval, immutable release, CLI, and an MCP
control surface. The current extraction also implements ScopeBinding, selected
Runtime serving, a small authenticated HTTP boundary, and a container host.
Multi-replica storage, durable background jobs, and organization-specific
identity/audit adapters remain scale-out work rather than new product concepts.

OC Team currently contains four kinds of behavior:

1. Contexture-native Profile, Skill, Tool, and MCP declarations;
2. typed roster queries and assignment validation;
3. Draft, acquisition, learning, evaluation, and evolution workflows;
4. OC-specific Hands, Hermes collaboration, storage, telemetry, permissions,
   and Project integration.

The existing `ProfileCatalog` port and authorization callbacks are useful
extraction seams. The stateful workflows still use OC-shaped records and must
be translated into the existing Blueprint lifecycle rather than copied.

## 4. Core contracts

### 4.1 Workspace

Workspace is the authoring container currently stored under the legacy
`project_id` field. It owns source records, normalized units, Blueprints,
evaluations, approvals, builds, and releases. The field remains compatible in
v1; adding a second record or an immediate storage rename would add migration
risk without changing product behavior. Workspace is never a consumer business
Scope.

### 4.2 ExpertNet

The existing published release remains the deployable ExpertNet. Roles inside
the release have stable Contexture refs derived from the reviewed Blueprint.
OC Profile declarations imported into a Blueprint retain provenance to their
source pack and original name.

### 4.3 ScopeBinding

ScopeBinding is the only new durable relationship.

```text
binding_id: stable record identifier
scope_ref: opaque non-empty URI-shaped reference
release_id: exact immutable ExpertNet release
role_selectors: zero or more Contexture selectors
enabled: operational switch
revision: optimistic-concurrency revision
created_at / updated_at: audit timestamps
```

Rules:

- an empty selector list means the complete ExpertNet release;
- selectors must pass Contexture `SurfaceSelection` validation against the
  release graph before the binding can be enabled;
- a binding never points to a mutable Blueprint or channel;
- changing release or selectors creates a reviewed revision;
- deletion is represented by disabling the record so audit history survives;
- duplicate active tuples of scope, release, and canonical selectors are
  rejected.

Personal mode may list all enabled releases without creating bindings. A
binding is needed only when the consumer supplies a business Scope.

### 4.4 Authorization boundary

Personal mode is a trusted local process. The current remote API authenticates
one service client with a bearer credential and records its supplied actor
label. OC authorizes its own user and Project before that service client asks
for an OC-owned `scope_ref`; ExpertCompose then requires an enabled binding.

Before a multi-tenant public service is offered, the same use cases must accept
an organization identity/policy adapter and partition repository queries at
the storage boundary. Filtering an unrestricted result is not tenant
isolation. This is an implementation port, not another durable product model.

### 4.5 Management and runtime interfaces

The complete authoring lifecycle remains available through CLI and MCP. A
small versioned HTTP/JSON boundary exists for service consumers:

```text
/healthz and /readyz
/v1/projects
/v1/projects/{id}/source-packs
/v1/projects/{id}/revisions
/v1/projects/{id}/supersede
/v1/projects/{id}/{build,evaluate,approve,publish}
/v1/releases
/v1/catalog?scope_ref=...
/v1/releases/{release_id}/catalog?scope_ref=...
/v1/scope-bindings
```

The catalog response revalidates publication and the full Blueprint digest,
removes local paths, applies the enabled ScopeBinding, and returns a digest for
the selected Blueprint. Upload and durable-job endpoints are added only when
remote asynchronous authoring is implemented.

OC capability acquisition, learning, and Skill evolution remain OC workflows
because they use OC Sessions, Hands, Projects, and permissions. Their reviewed
content converges at the existing Draft decision: a configured service imports
the exact Draft as evidence and creates the next ordinary Blueprint. Approval
then runs the existing build, evaluation, approval, publication, and
ScopeBinding switch. Thus OC still owns who may decide, while ExpertCompose is
the sole writer of reusable team content.

Agent use goes through a separate Runtime MCP endpoint. It loads a pinned
ExpertNet release, derives a Contexture ceiling from authorized ScopeBindings,
and allows the request header to narrow that ceiling further.

The initial service runs these operations synchronously. Durable jobs are a
scale-out adapter, not a new product concept.

## 5. Personal and enterprise editions

Both editions execute the same application use cases and domain rules.

| Concern | Personal host | Enterprise host |
|---|---|---|
| Identity | implicit local actor | authenticated principal |
| Authorization | trusted local adapter | policy adapter |
| Metadata | SQLite | SQLite initially; replaceable repository before scale-out |
| Artifacts | local filesystem | durable volume initially; object adapter later |
| Work execution | in process | synchronous initially; durable worker later |
| MCP | stdio or loopback | authenticated HTTPS |
| Audit | local manifests | append-only audit sink |

The server is a modular application with separate API and worker entry points.
Compiler, registry, and Runtime modules remain in one codebase. A module is
split into another service only when it needs an independent security boundary
or measured scaling policy.

## 6. OC extraction mapping

### 6.1 Moves to ExpertCompose behavior

- Profile content and hierarchy become Role content in a Blueprint.
- Skill bodies and reviewed Tool requirements/bindings become Blueprint data.
- roster queries read Role metadata from a released ExpertNet projection.
- Team Draft content becomes a new Blueprint draft/version.
- capability acquisition imports authorized evidence into a Workspace.
- session learning proposes evidence and a new Blueprint version.
- skill evolution produces candidate Blueprint content and evaluation results;
  it cannot modify a published release directly.

### 6.2 Remains in OC

- Project lifecycle and `project://` identity;
- directory-to-Project binding;
- Account and Project membership;
- Authorization for OC resources;
- Work and automation;
- Hand placement and Hermes session operation;
- OC-specific business Tools and their final operation authorization;
- OC-specific expert source pack.

### 6.3 Compatibility adapter

During migration OC keeps its existing Team facade. A new adapter projects an
ExpertNet release into the existing immutable `ProfileDescriptor` view. Work
and Automation therefore retain their current call shape while the source of
the roster changes.

The adapter maps:

```text
Role name              -> ProfileDescriptor.name
Role description       -> description
Role path parent       -> division compatibility label
Skill refs             -> skills
Tool/MCP requirements  -> connectors and mcp_bindings projection
OC pack annotations    -> hand, model, fallback_hands, plugins
ScopeBinding           -> project applicability during compatibility period
```

Runtime placement remains an OC decision. ExpertCompose does not assign a Hand.

## 7. Data migration and cutover

Each state transfer uses a versioned, deterministic export with content
digests. Import is idempotent and records the source repository revision.

The cutover sequence is:

1. import Profile/Skill/Tool declarations as an OC ExpertNet source pack;
2. compare roster and assignment projections in shadow reads;
3. make ExpertCompose release projection authoritative for roster reads;
4. route new Team Drafts through Blueprint creation;
5. migrate active acquisition and learning records or finish them in OC;
6. switch evolution proposals to ExpertCompose evaluation/publication;
7. remove OC implementations only after their functional contract is green
   against the adapter.

Long-lived dual writes are prohibited. Stateful cutover uses a bounded write
freeze, one idempotent import, verification, and an adapter switch. The old
tables remain read-only until rollback expiry.

## 8. Testing contract

### 8.1 Contexture independent gate

Run the repository's complete local gate. Add or retain focused evidence for
selector validation, subtree projection, direct-access denial, principal
ceiling intersection, fixed selection, and request concurrency isolation.

### 8.2 ExpertCompose independent gate

Prove:

- ScopeBinding validation, persistence, concurrency, disable, and exact release
  pinning;
- personal mode without identity infrastructure;
- remote policy denial before repository or artifact disclosure;
- generated and hosted Runtime selection;
- deterministic OC pack import;
- unchanged evidence/evaluation/approval/publication invariants;
- CLI, Studio MCP, management HTTP, and Runtime MCP smoke behavior;
- package build and clean installation.

### 8.3 OC independent and functional gate

Unit and integration tests prove the compatibility adapter. Functional tests
must start the ExpertCompose test server, create or load a released OC
ExpertNet, create a project Scope binding, authenticate two callers with
different project access, and verify:

- the allowed caller sees and invokes the bound Role subtree;
- an unbound or unauthorized caller cannot discover or invoke it;
- roster and assignment behavior matches the frozen legacy contract;
- OC Project Tools still perform their own authorization;
- disabling a binding removes the expert surface without changing the Project;
- ExpertCompose unavailability produces an explicit degraded result and never
  grants a wider local roster.

## 9. Deployment and operations

Personal release ships one Python distribution and local migration tooling.

The first shared deployment is intentionally one API process and an optional
MCP process over one durable Workspace volume. SQLite remains a single-writer
deployment constraint. Health/readiness, bearer authentication, bounded JSON
requests, immutable releases, exact ScopeBindings, an OC fail-closed client,
and a configuration rollback are implemented and container-tested. A consumer
may stay pinned to an exact release, or resolve the single enabled binding for
a Scope. Scope resolution fails closed when zero or multiple bindings are
enabled; an approved OC revision switches the binding only in Scope-resolved
mode. Exact-release deployments require an explicit configuration update.

Only measured demand for multiple replicas or long background work justifies
the later repository/object-store/worker adapters. That upgrade changes hosts,
not Workspace, Blueprint, ExpertNet, ScopeBinding, or the three-product
ownership boundary.

## 10. Deferred decisions

The initial decoupling does not add a Namespace aggregate, general policy
language, marketplace, billing model, arbitrary graph database, or additional
microservices. Tags, multi-category discovery, richer Scope inheritance, and
enterprise packaging are revisited only after the minimal contracts have real
usage evidence.

