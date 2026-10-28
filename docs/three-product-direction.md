# Contexture, ExpertCompose, and one-creator

Status: authoritative product direction  
Last updated: 2026-10-28

```text
one-creator                  Project / Scope / Authorization
     |  maps an authorized Scope to an exact released team
     v
ExpertCompose                source -> Blueprint -> ExpertNet
     |  renders the team
     v
Contexture                   Role / Skill / Tool
```

The three products stay independent:

- **Contexture** runs selected Role/Skill/Tool surfaces. It knows nothing about
  projects, users, or business authorization.
- **ExpertCompose** makes, evaluates, publishes, and serves expert teams. An
  **ExpertNet is the team**.
- **one-creator** owns projects, collaboration, authorization, Work, Hands,
  Hermes sessions, and project Tools.

The design adds only one durable relationship:

```text
ScopeBinding: project://apollo -> release rel_123 -> team/engineering/*
```

`scope_ref` is opaque to ExpertCompose: the Scope owner interprets and
authorizes it. A binding pins an immutable release. A Role path already handles
organization and routing, so there is no Namespace or second Team model.

Personal and enterprise ExpertCompose use one codebase. Personal mode runs
locally without a permission system; enterprise mode adds identity,
authorization, audit, and scalable storage at the host boundary.

Complete durable vocabulary for this phase:

```text
Contexture:    Role / Skill / Tool
ExpertCompose: Workspace / Blueprint / ExpertNet / ScopeBinding
one-creator:   Project / Scope / Authorization
```
