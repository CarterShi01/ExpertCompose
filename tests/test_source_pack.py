from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from expertcompose.service import ExpertComposeService
from expertcompose.source_pack import TeamSourcePack, source_pack_digest


def _pack() -> dict[str, object]:
    skill_instructions = "Inspect boundaries, state the tradeoffs, and record evidence."
    role_instructions = (
        "Review the system before changing it. api_key=abcdefghijklmnop must be redacted."
    )
    research_instructions = "Compare source claims and preserve contradictory evidence."
    value: dict[str, object] = {
        "format": "expertcompose.source-pack.v2",
        "name": "sample-team",
        "title": "Sample Team",
        "objective": "Provide a small reviewed team without executing imported source text.",
        "roles": [
            {
                "name": "architect",
                "description": "Review system boundaries and contracts.",
                "instructions": role_instructions,
                "path": ["engineering"],
                "skills": ["architecture-review"],
                "tools": ["lookup-evidence"],
                "annotations": {
                    "oc.hand": "claude-code",
                    "oc.division": "engineering",
                },
            },
            {
                "name": "researcher",
                "description": "Compare claims across sources.",
                "instructions": research_instructions,
                "path": ["research"],
                "skills": ["architecture-review"],
                "tools": ["lookup-evidence"],
                "annotations": {"oc.hand": "hermes", "oc.division": "research"},
            },
        ],
        "skills": [
            {
                "name": "architecture-review",
                "description": "Perform an evidence-backed architecture review.",
                "instructions": skill_instructions,
                "uses": ["project/get-project", "project/resource/read"],
            }
        ],
        "messages": [
            {"role": "role:architect", "content": role_instructions},
            {"role": "role:researcher", "content": research_instructions},
            {"role": "skill:architecture-review", "content": skill_instructions},
        ],
    }
    value["content_sha256"] = source_pack_digest(value)
    return value


def test_source_pack_import_is_deterministic_grounded_and_redacted(
    service: ExpertComposeService,
    tmp_path: Path,
) -> None:
    path = tmp_path / "team-pack.json"
    path.write_text(json.dumps(_pack()), encoding="utf-8")
    blueprint = service.import_source_pack(
        "literature-review",
        path,
        authorization="Repository-owned reviewed pack",
        created_by="pytest",
    )
    assert blueprint.provider == "source-pack-v1"
    assert blueprint.roots[0].name == "team"
    group = blueprint.roots[0].children[0]
    assert group.name == "engineering"
    role = group.children[0]
    assert role.name == "architect"
    assert role.annotations["oc.hand"] == "claude-code"
    assert role.skills[0].name == "architecture-review"
    assert role.skills[0].uses == (
        "project/get-project", "project/resource/read",
    )
    assert "abcdefghijklmnop" not in role.instructions
    assert "[REDACTED]" in role.instructions
    assert role.evidence_refs
    build = service.build("literature-review", blueprint.blueprint_id)
    assert build.unbound_required_tools == ()
    manifest = json.loads((build.path / "build-manifest.json").read_text())
    assert manifest["host_uses"] == ["project/get-project", "project/resource/read"]
    generated = (build.path / "src" / build.package / "app.py").read_text()
    assert "project/get-project" not in generated
    assert "project/get-project" in (build.path / "README.md").read_text()
    assert service.evaluate("literature-review", blueprint.blueprint_id).status == "passed"
    service.approve(
        "literature-review", blueprint.blueprint_id, approved_by="domain-reviewer"
    )
    release = service.publish(
        "literature-review", blueprint.blueprint_id, published_by="release-manager"
    )
    service.create_scope_binding(
        scope_ref="project://engineering",
        release_id=release.release_id,
        role_selectors=("team/engineering",),
        created_by="pytest",
    )
    catalog = service.release_catalog(
        release.release_id, scope_refs=("project://engineering",)
    )
    assert catalog["catalog_sha256"] != release.blueprint_sha256
    selected_team = catalog["blueprint"]["roots"][0]
    assert [child["name"] for child in selected_team["children"]] == ["engineering"]


def test_source_pack_digest_and_instruction_projection_are_verified() -> None:
    value = _pack()
    value["content_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="content_sha256"):
        TeamSourcePack.model_validate(value)

    value = _pack()
    messages = list(value["messages"])  # type: ignore[arg-type]
    messages[0] = {"role": "role:architect", "content": "different"}
    value["messages"] = messages
    value["content_sha256"] = source_pack_digest(value)
    with pytest.raises(ValidationError, match="exactly mirror"):
        TeamSourcePack.model_validate(value)

    value = _pack()
    value["format"] = "expertcompose.source-pack.v1"
    value["content_sha256"] = source_pack_digest(value)
    with pytest.raises(ValidationError, match="v1 cannot declare Skill uses"):
        TeamSourcePack.model_validate(value)

    value = _pack()
    skills = list(value["skills"])  # type: ignore[arg-type]
    skills[0] = {**skills[0], "uses": ["not a ref"]}
    value["skills"] = skills
    value["content_sha256"] = source_pack_digest(value)
    with pytest.raises(ValidationError, match="invalid uses ref"):
        TeamSourcePack.model_validate(value)

    value = _pack()
    value["format"] = "expertcompose.source-pack.v1"
    for skill in value["skills"]:  # type: ignore[union-attr]
        skill["uses"] = []
    value["content_sha256"] = source_pack_digest(value)
    assert TeamSourcePack.model_validate(value).format == "expertcompose.source-pack.v1"
