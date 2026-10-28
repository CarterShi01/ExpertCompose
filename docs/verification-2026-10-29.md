# Three-product decoupling verification record

Date: 2026-10-29 (Asia/Shanghai)
Scope: local acceptance of the minimal Contexture / ExpertCompose / one-creator
integration. This is not a claim that a production environment was changed.

## Revisions under test

- Contexture: `089585d525082d083076c421152bf4786ad6c666`
- ExpertCompose implementation: `838583f3f5d40a44e4e57d3247232503fddfd208`
- one-creator final integration: `7d74173e5821c14cccfd7dab8e051e3dbc87a19a`

Contexture remained unchanged and matched `origin/master`. ExpertCompose and
one-creator were tested as independently started products; neither imports the
other product's persistence implementation.

## Contexture

The complete repository gate passed:

- `uv run --extra dev pytest -q`: 507 tests and 546 subtests passed.
- `uv run --extra dev pyright`: no errors.
- Ruff, pyproject validation, porting-contract verification, product manifest,
  incremental manifest, and release-binding verification passed.

No Contexture change was needed. Its existing surface selection and ceiling
are sufficient for a selected ExpertNet Runtime; business Scope remains above
the framework.

## ExpertCompose

The complete development gate passed:

- 26 tests passed.
- Pyright reported 0 errors; Ruff passed.
- Source distribution and wheel built successfully.
- CLI help and a clean-wheel installation passed, including CLI, MCP, API, and
  Blueprint revision imports from the installed wheel.

The final container image passed an authenticated remote lifecycle:

1. readiness succeeded and an unauthenticated `/v1/releases` request returned
   401;
2. a reviewed source pack was built, evaluated, approved, and published as
   `rel_7491addf06d3c0926b348998`;
3. an evidence-backed Skill revision was independently built, evaluated,
   approved, and published as `rel_7f98d4ec0d8a9d8cedaee9eb`;
4. two enabled ScopeBindings caused catalog resolution to fail closed;
5. disabling the old binding selected the second approved release; and
6. after a container restart, the named volume still resolved the second
   release and its `reviewer` Role.

The disposable acceptance containers and volumes were removed after the test.

## one-creator

Focused Team tests passed for Draft governance, immutable catalog projection,
cutover, HTTP failure behavior, and deterministic source-pack export.

Against a separately started ExpertCompose process:

- the exact-release and Scope-resolved adapters each reproduced all 38 legacy
  Profile descriptors row for row;
- the initial OC ExpertNet published as `rel_fc38f2f31abef1014ebcbcee`;
- a reviewed OC Draft produced a normal Blueprint revision, passed the same
  governance gates, published as `rel_b32b9fd46dd237c2e69bd2ed`, and switched
  the ScopeBinding; and
- unavailable service, unauthorized access, zero binding, and ambiguous
  binding paths failed closed in their focused tests.

The repository-native offline gate passed at commit
`5efb08117341b4aac85f53b070f1e7333aea73c3`:

- receipt: `.oc/verification/20261028T160927Z-offline/receipt.json` in the clean
  acceptance worktree;
- 71 steps passed in 1,441.485 seconds;
- all 13 serial real-browser journeys passed in 16.6 minutes;
- all 33 isolated owner-module contract checks passed;
- the application compiled as 77 Roles, 62 Skills, and 367 Tools; and
- capability, Client, Runtime, Architecture, Role-map, deployment, source-lock,
  generated-runtime, final-architecture, and repository-hygiene gates passed.

The latest upstream OC changes introduced `work/list-comments` without its two
exact inventory entries. The integration adds that read-only Tool to the
capability and wire baselines and changes only the corresponding exact routing
count from 366 to 367; no assertion or gate was weakened.

Two later upstream OC commits added the managed Omnigent Runtime and Client
cache. They were merged without changing ExpertCompose integration code. On
the final commit, Client and Omnigent release freshness, 25 agent-adapter tests,
13 Omnigent-connect tests, Host lifecycle, source locks, Runtime provider, and
ExpertCompose Team cutover all passed before publication to `origin/master`.

## Project Type extension acceptance

A later additive acceptance covered mandatory Project Type Roles without
changing the three-product ownership boundary:

- ExpertCompose commits `4fd2485` and `07a5e0c` added source-pack v2 Skill
  `uses`, explicit Host composition dependencies, and version-correct import
  provenance;
- one-creator commit `b71c5c88` exported 40 Roles and 14 Skills from source-pack
  digest `082194874aa5125f9e2f2d7f471ecbdf3d646432694187fce16be0759bdcdc03`;
- Blueprint `bp_c189cf823ac7c143682311ee` passed all deterministic release
  gates and compiled to 137 canonical Contexture refs; the optional behavioral
  receipt check was explicitly skipped because no Host observations were
  supplied;
- immutable release `rel_4441479dab08e22423d18404` was published in the durable
  user-level Workspace and enabled for `project://one-creator` through binding
  `bind_0e81abb3426dcc25e08939fc`; and
- Scope catalog verification recovered both `team/project/goal` and
  `team/project/area`, including their Host-owned `project/...` dependencies.

ExpertCompose's 26-test suite, Ruff, Pyright (0 errors), sdist/wheel build and
CLI smoke gate passed for the bridge. one-creator's Project/Team contract
checks, generated Role-map and capability-manifest checks, Panel tests, Web
lint/build, and 16 core browser-contract tests passed for the consuming change.
As elsewhere in this record, the release is local acceptance evidence and not
a claim that a production database or public service was changed.

## Acceptance boundary

This record proves the local/container MVP and the independent product
boundary. It does not claim a public package or image publication, a production
database migration, or migration of unknown live pending Drafts. General
uploads, durable asynchronous jobs, multi-replica metadata/object storage, and
removal of the bounded OC rollback adapter remain explicitly deferred scale-out
or production-cutover work; they do not add product concepts.
