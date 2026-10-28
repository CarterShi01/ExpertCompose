# Local one-creator Team module reference

Reviewed source: sibling repository `one-creator`, especially
`oc_app/modules/team` and `oc_app/capabilities/team`, on 2026-10-28. This is a
local architectural study, not copied source and not an external dependency.

## Structure observed

The Team module separates five responsibilities:

1. `domain/` contains pure selectors, validation and draft-decision policies.
2. `application/` contains use cases, actors/permissions, and storage/catalog
   Protocol ports.
3. `adapters/` and `providers/` implement filesystem, SQL, telemetry, discovery
   and external capability concerns.
4. `api/` exposes typed descriptors and a facade instead of leaking Contexture
   Role objects to peer modules.
5. `capabilities/team/` projects the business system into a lazy Contexture
   Role tree. Profiles and Skills remain declarations; draft construction and
   governance remain application behavior.

Two decisions are particularly relevant. First, a construction subsystem can
submit an idempotent draft but cannot grant itself decision authority. Second,
approved declarations are projected as typed descriptors across module
boundaries, rather than passing live runtime graph nodes around.

## ExpertCompose mapping

| one-creator Team layer | ExpertCompose v0.1 equivalent | Shared principle |
|---|---|---|
| Domain policies and descriptors | `models.py`, evaluation rules, governance transitions | Pure typed records and explicit transitions |
| Application service and ports | `service.py`, `SynthesisProvider` Protocol | One use-case facade; providers depend on a narrow port |
| Catalog/storage adapters | `workspace.py`, `ingestion.py` | Persistence and formats remain outside expert declarations |
| Capability providers | `synthesis.py`, `generator.py` | Provider output is converted through product contracts |
| Typed public API | `ExpertComposeService` and Pydantic records | Do not expose Contexture node instances as product state |
| Contexture Team Role | `mcp.py` and generated ExpertNet applications | Runtime graph is a projection, not the database |
| DraftDecision governance | Blueprint → evaluation → approval → release | The builder cannot self-approve |

## Adaptations made for an independent product

ExpertCompose adds provenance and compiler stages that the operational Team
catalog does not need: immutable sources, normalized units, evidence/claim/
procedure/task IR, deterministic target generation, artifact hashes, neutral
behavioral receipts, and standalone releases.

It also names the generated structure `ExpertNet` rather than treating every
expert as a flat roster Profile. Contexture Roles can form responsibility trees
and carry Skills and bound Tools at the correct scope.

The MVP does not reproduce one-creator's many deployment-specific adapters,
Hermes usage collection, tenant permissions, UI projections, or external MCP
catalog. Those belong in later adapters once ExpertCompose has equivalent
requirements. Pulling them in now would couple an independent product to one
host.

## Scale-up rule

The current focused files are layer-equivalent, but not directory-isomorphic.
When a second implementation appears in any area—for example object storage
beside local workspace, multiple target generators, or multiple evaluation
runners—that area should become a package with explicit `domain`,
`application/ports`, `adapters/providers`, and `api` modules. Contexture
declarations must remain in the interface/capability edge and must never become
the persistence model. This retains one-creator's strongest boundary without
adding package ceremony before it creates isolation.
