from __future__ import annotations

from expertcompose.models import BlueprintStatus
from expertcompose.service import ExpertComposeService
from expertcompose.source_pack import source_pack_digest


def _pack() -> dict[str, object]:
    role = "Review evidence before accepting a claim."
    skill = "Check the cited source and record unsupported claims."
    value: dict[str, object] = {
        "format": "expertcompose.source-pack.v1",
        "name": "revision-team",
        "title": "Revision Team",
        "objective": "Exercise evidence-backed team revisions.",
        "roles": [{
            "name": "reviewer",
            "description": "Reviews source-grounded work.",
            "instructions": role,
            "path": ["quality"],
            "skills": ["source-review"],
            "tools": ["lookup-evidence"],
            "annotations": {
                "oc.profile_name": "reviewer",
                "oc.hand": "claude-code",
                "oc.project": "*",
                "oc.division": "quality",
                "oc.model": "",
                "oc.fallback_hands": [],
                "oc.connectors": [],
                "oc.mcp_bindings": [],
                "oc.plugins": [],
                "oc.is_orchestrator": False,
                "oc.compatible_harnesses": ["claude-code"],
            },
        }],
        "skills": [{
            "name": "source-review",
            "description": "Review source provenance.",
            "instructions": skill,
        }],
        "messages": [
            {"role": "role:reviewer", "content": role},
            {"role": "skill:source-review", "content": skill},
        ],
    }
    value["content_sha256"] = source_pack_digest(value)
    return value


def _release(service: ExpertComposeService) -> str:
    blueprint = service.import_source_pack_value(
        "literature-review",
        _pack(),
        authorization="reviewed test pack",
        created_by="pytest",
    )
    service.build("literature-review", blueprint.blueprint_id)
    assert service.evaluate("literature-review", blueprint.blueprint_id).status == "passed"
    service.approve(
        "literature-review", blueprint.blueprint_id, approved_by="reviewer"
    )
    return service.publish(
        "literature-review", blueprint.blueprint_id, published_by="publisher"
    ).release_id


def test_reviewed_change_creates_an_idempotent_grounded_blueprint(
    service: ExpertComposeService,
) -> None:
    release_id = _release(service)
    body_value = {
        "proposal": {
            "schema": "oc.team-capability-change/1",
            "operation": "improve",
            "capability": {
                "kind": "skill",
                "name": "source-review",
                "description": "Review exact source provenance and contradictions.",
            },
            "target": {"role": "reviewer"},
            "adaptation": {
                "instructions": "Verify exact sources and preserve contradictory evidence.",
                "status": "prepared",
            },
        }
    }
    change = {
        "kind": "skill",
        "name": "source-review",
        "target_scope": "resource",
        "title": "Improve source review",
        "reason": "Representative target-Hand validation passed.",
        "effect": "Improve the reviewer Skill.",
        "source": "team-construction:test",
        "idempotency_key": "change-1",
        "body": "reviewed YAML body",
        "body_value": body_value,
    }
    revised = service.revise(
        "literature-review",
        base_release_id=release_id,
        change=change,
        authorization="OC reviewer submitted this exact change",
        created_by="oc-reviewer",
    )
    duplicate = service.revise(
        "literature-review",
        base_release_id=release_id,
        change=change,
        authorization="OC reviewer submitted this exact change",
        created_by="oc-reviewer",
    )
    assert duplicate.blueprint_id == revised.blueprint_id
    role = revised.roots[0].children[0].children[0]
    assert role.skills[0].instructions.startswith("Verify exact sources")
    assert len(revised.source_ids) == 2
    service.build("literature-review", revised.blueprint_id)
    report = service.evaluate("literature-review", revised.blueprint_id)
    assert report.status == "passed"


def test_reviewed_role_can_be_added_or_dismissed(
    service: ExpertComposeService,
) -> None:
    release_id = _release(service)
    revised = service.revise(
        "literature-review",
        base_release_id=release_id,
        authorization="Founder-reviewed role proposal",
        created_by="founder",
        change={
            "kind": "scope-change",
            "name": "fact-checker",
            "target_scope": "role",
            "title": "Fact checker",
            "reason": "Add an explicitly routed reviewer.",
            "effect": "Available in the OC quality division.",
            "source": "cockpit",
            "idempotency_key": "role-1",
            "body": "description: Check facts\nlabels:\n  hand: claude-code",
            "body_value": {
                "description": "Check facts against exact evidence.",
                "labels": {"hand": "claude-code", "project": "*"},
            },
        },
    )
    added = revised.roots[0].children[-1]
    assert added.name == "fact-checker"
    assert added.annotations["oc.profile_name"] == "fact-checker"
    dismissed = service.supersede("literature-review", revised.blueprint_id)
    assert dismissed.status is BlueprintStatus.SUPERSEDED
    assert service.supersede("literature-review", revised.blueprint_id) == dismissed


def test_scope_catalog_fails_closed_on_ambiguous_bindings(
    service: ExpertComposeService,
) -> None:
    first = _release(service)
    service.create_scope_binding(
        scope_ref="project://one-creator",
        release_id=first,
        created_by="pytest",
    )
    assert service.scope_catalog("project://one-creator")["release"]["release_id"] == first

    change = {
        "kind": "skill",
        "name": "source-review",
        "target_scope": "resource",
        "title": "Second release",
        "reason": "Create an intentionally competing binding.",
        "effect": "Test fail-closed selection.",
        "source": "test",
        "idempotency_key": "second",
        "body": "skill_md: Verify exact citations.",
        "body_value": {"skill_md": "Verify exact citations before reporting."},
    }
    revised = service.revise(
        "literature-review",
        base_release_id=first,
        change=change,
        authorization="test",
        created_by="pytest",
    )
    service.build("literature-review", revised.blueprint_id)
    service.evaluate("literature-review", revised.blueprint_id)
    service.approve("literature-review", revised.blueprint_id, approved_by="pytest")
    published = service.publish(
        "literature-review", revised.blueprint_id, published_by="pytest"
    )
    second = published.release_id
    assert service.publish(
        "literature-review", revised.blueprint_id, published_by="pytest"
    ) == published
    service.create_scope_binding(
        scope_ref="project://one-creator",
        release_id=second,
        created_by="pytest",
    )
    try:
        service.scope_catalog("project://one-creator")
    except ValueError as error:
        assert "multiple enabled bindings" in str(error)
    else:
        raise AssertionError("ambiguous ScopeBindings did not fail closed")
