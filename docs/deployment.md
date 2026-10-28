# Deployment and OC cutover

ExpertCompose has one codebase and two deployment shapes. Personal use runs the
CLI or stdio MCP against a local Workspace. Shared use runs the same package as
an HTTP API and, when needed, a streamable-HTTP MCP server. There is no separate
enterprise fork and no second Team model.

## Local and container startup

Personal MCP:

```bash
expertcompose --workspace .expertcompose serve --transport stdio
```

Authenticated HTTP API:

```bash
export EXPERTCOMPOSE_API_TOKEN='replace-with-a-secret'
expertcompose --workspace /var/lib/expertcompose api --host 0.0.0.0 --port 8090
```

The API refuses a non-loopback listener without a token. `/healthz` and
`/readyz` are intentionally unauthenticated; every `/v1` route requires the
configured bearer credential. Terminate TLS and apply organization identity at
the ingress. The v1 service itself accepts only a deployment credential and an
audited actor label; it does not copy OC's authorization model.

The v1 API can create a Workspace, submit a bounded reviewed source pack, and
run build/evaluate/approve/publish synchronously. General document upload and
durable background jobs remain on the later scale-out path; CLI/MCP retain the
complete local authoring surface.

For a local container rehearsal:

```bash
cp .env.example .env
docker compose --env-file .env -f deploy/compose.yaml up --build -d expertcompose-api
curl --fail http://127.0.0.1:8090/readyz
```

The named volume is the durable Workspace. Back it up before upgrade. The MVP
uses one SQLite-backed writer with synchronous jobs; run one API replica. A
future multi-replica installation may replace the persistence and job adapters,
without changing Blueprint, ExpertNet, or ScopeBinding.

## Publish and bind

Use CLI or MCP to ingest evidence, compose, build, evaluate, approve, and
publish. Publication returns an immutable `release_id`. Then bind an OC Scope
to that exact release:

```bash
# Run in the one-creator repository. The exporter writes only inert JSON.
python -m oc_app.capabilities.team.source_pack > /secure/oc-team.json

# Run against the ExpertCompose Workspace.
expertcompose --workspace /var/lib/expertcompose project create one-creator-team \
  --title 'one-creator Team' --objective 'Publish the reviewed OC expert team'
expertcompose --workspace /var/lib/expertcompose import-pack one-creator-team \
  /secure/oc-team.json --authorization 'reviewed OC repository declarations'
```

Build, evaluate, approve, and publish that Blueprint through the normal gates.
Then create the mapping:

```bash
expertcompose --workspace /var/lib/expertcompose binding create \
  project://one-creator rel_REPLACE_ME --select 'team/*' --created-by release-manager
```

The API returns the Blueprint only after validating publication, digest, and an
enabled ScopeBinding. It removes local artifact paths from responses and trims
the Role tree to the selected surface.

## OC configuration

Configure OC with an exact release; never use a mutable "latest" alias:

```bash
export OC_EXPERTCOMPOSE_URL='http://expertcompose-api:8090'
export OC_EXPERTCOMPOSE_RELEASE_ID='rel_REPLACE_ME'
export OC_EXPERTCOMPOSE_SCOPE_REF='project://one-creator'
export OC_EXPERTCOMPOSE_TOKEN="$EXPERTCOMPOSE_API_TOKEN"
export OC_EXPERTCOMPOSE_TIMEOUT_SECONDS='5'
export OC_EXPERTCOMPOSE_RETRIES='2'
```

OC keeps Project authorization and Hand placement. ExpertCompose supplies the
released Profile/Skill catalog through the existing OC Team facade. If the
remote service denies the Scope or is unavailable before OC has loaded the
immutable release, Team reads fail explicitly; OC does not silently use a
different catalog.

Run the external functional smoke from the OC repository:

```bash
python -m oc_app.tests.check_team_expertcompose_external
```

## Cutover and rollback

1. Export OC declarations and publish the resulting ExpertNet.
2. Compare the released roster, selectors, and assignments with the legacy
   catalog while OC still uses the legacy source.
3. Create the exact ScopeBinding and run the external smoke.
4. Set the OC remote variables and restart one canary instance.
5. Verify Team, Work, Automation, Project, and runtime behavior, then roll the
   remaining instances.

Rollback is configuration-only during the compatibility window: remove
`OC_EXPERTCOMPOSE_URL`, `OC_EXPERTCOMPOSE_RELEASE_ID`, and
`OC_EXPERTCOMPOSE_SCOPE_REF`, then restart OC to use its legacy declarations.
Do not delete the published release or legacy declarations until the rollback
window is closed. Disabling a ScopeBinding is an emergency deny action, not a
transparent fallback.
