"""Evidence-backed revisions of an existing published ExpertNet Blueprint.

A revision is not another durable product model. It imports one reviewed change
as evidence and produces the next ordinary Blueprint version. The caller still
has to build, evaluate, approve, and publish that Blueprint.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from .ingestion import Ingestor
from .models import (
    BlueprintStatus,
    Evidence,
    EvidenceKind,
    ExpertBlueprint,
    ReleaseStatus,
    RoleBlueprint,
    SkillBlueprint,
    SourceKind,
    require_name,
    stable_id,
    utc_now,
)
from .workspace import Workspace


class BlueprintReviser:
    """Turn one bounded, reviewed change into the next Blueprint version."""

    def __init__(self, workspace: Workspace, ingestor: Ingestor) -> None:
        self.workspace = workspace
        self.ingestor = ingestor

    def submit(
        self,
        project_id: str,
        *,
        base_release_id: str,
        change: dict[str, Any],
        authorization: str,
        created_by: str,
    ) -> ExpertBlueprint:
        normalized = _validated_change(change)
        raw = json.dumps(
            normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        change_sha256 = hashlib.sha256(raw).hexdigest()
        blueprint_id = stable_id("bp", project_id, base_release_id, change_sha256)
        for existing in self.workspace.list_blueprints(project_id):
            if existing.blueprint_id == blueprint_id:
                return existing

        base = self._published_blueprint(project_id, base_release_id)
        source, _created = self.ingestor.import_bytes(
            project_id,
            raw,
            kind=SourceKind.TEXT,
            origin=f"api://reviewed-revision/{change_sha256}",
            authorization=authorization,
            title=str(normalized["title"]),
            license="proprietary",
        )
        unit = self.workspace.source_units(project_id, source.source_id)[0]
        evidence = Evidence(
            evidence_id=stable_id("ev", source.source_id, unit.sha256),
            source_id=source.source_id,
            locator=unit.locator,
            kind=EvidenceKind.DECISION,
            summary=str(normalized["reason"])[:2000],
            excerpt=unit.text[:4000],
            sha256=unit.sha256,
            confidence=1.0,
            tags=("reviewed-revision", str(normalized["kind"]), str(normalized["name"])),
        )
        evidence_rows = {
            item.evidence_id: item
            for item in (
                Evidence.model_validate(value)
                for value in self.workspace.load_evidence(project_id)
            )
        }
        evidence_rows[evidence.evidence_id] = evidence
        self.workspace.save_evidence(project_id, evidence_rows.values())

        roots = _apply_change(base.roots, normalized, evidence.evidence_id)
        roots = tuple(
            root.model_copy(
                update={
                    "evidence_refs": tuple(
                        dict.fromkeys((*root.evidence_refs, evidence.evidence_id))
                    )
                }
            )
            for root in roots
        )
        blueprint = base.model_copy(
            update={
                "blueprint_id": blueprint_id,
                "version": self.workspace.next_blueprint_version(project_id),
                "status": BlueprintStatus.DRAFT,
                "roots": roots,
                "source_ids": tuple(
                    dict.fromkeys((*base.source_ids, source.source_id))
                ),
                "created_at": utc_now(),
                "created_by": created_by,
                "provider": "reviewed-revision-v1",
            }
        )
        self.workspace.save_blueprint(blueprint)
        return blueprint

    def supersede(self, project_id: str, blueprint_id: str) -> ExpertBlueprint:
        blueprint = self.workspace.blueprint(project_id, blueprint_id)
        if blueprint.status is BlueprintStatus.APPROVED:
            raise ValueError("an approved Blueprint cannot be dismissed")
        if blueprint.status is BlueprintStatus.SUPERSEDED:
            return blueprint
        updated = blueprint.model_copy(update={"status": BlueprintStatus.SUPERSEDED})
        self.workspace.save_blueprint(updated)
        return updated

    def _published_blueprint(
        self, project_id: str, release_id: str
    ) -> ExpertBlueprint:
        release = self.workspace.release(release_id)
        if release.project_id != project_id:
            raise ValueError("base release does not belong to the target Workspace")
        if release.status is not ReleaseStatus.PUBLISHED:
            raise ValueError("a Blueprint revision requires a published base release")
        path = Path(release.artifact_path) / "expert-blueprint.json"
        blueprint = ExpertBlueprint.model_validate_json(path.read_text(encoding="utf-8"))
        if (
            blueprint.blueprint_id != release.blueprint_id
            or blueprint.canonical_sha256() != release.blueprint_sha256
        ):
            raise ValueError("base ExpertNet release failed Blueprint verification")
        return blueprint


def _validated_change(value: dict[str, Any]) -> dict[str, Any]:
    required = ("kind", "name", "target_scope", "title", "reason", "body", "body_value")
    result: dict[str, Any] = {}
    for key in required[:-1]:
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"reviewed change {key} must be a non-empty string")
        maximum = 50_000 if key == "body" else 4_000
        if len(item) > maximum:
            raise ValueError(f"reviewed change {key} exceeds {maximum} characters")
        result[key] = item.strip()
    body_value = value.get("body_value")
    if not isinstance(body_value, dict):
        raise ValueError("reviewed change body_value must be a JSON object")
    result["body_value"] = body_value
    result["name"] = require_name(str(result["name"]))
    if result["target_scope"] not in {"role", "resource"}:
        raise ValueError("reviewed change target_scope must be role or resource")
    for key in ("effect", "source", "idempotency_key"):
        item = value.get(key, "")
        if not isinstance(item, str) or len(item) > 4_000:
            raise ValueError(f"reviewed change {key} must be a bounded string")
        result[key] = item.strip()
    return result


def _apply_change(
    roots: tuple[RoleBlueprint, ...],
    change: dict[str, Any],
    evidence_id: str,
) -> tuple[RoleBlueprint, ...]:
    body = cast(dict[str, Any], change["body_value"])
    proposal_value = body.get("proposal", body)
    proposal = proposal_value if isinstance(proposal_value, dict) else body
    capability = proposal.get("capability")
    capability = capability if isinstance(capability, dict) else {}
    adaptation = proposal.get("adaptation")
    adaptation = adaptation if isinstance(adaptation, dict) else {}
    target = proposal.get("target")
    target = target if isinstance(target, dict) else {}

    kind = str(capability.get("kind") or change["kind"]).strip().lower()
    if kind in {"skill-evolution", "skill_evolution"}:
        kind = "skill"
    if kind not in {"role", "skill"}:
        kind = "role" if change["target_scope"] == "role" else "skill"
    name = require_name(str(capability.get("name") or change["name"]))
    operation = str(proposal.get("operation") or "").strip().lower()
    target_role = str(
        target.get("role")
        or body.get("target_role")
        or proposal.get("bind_to")
        or body.get("bind_to")
        or ""
    ).strip()
    description = str(
        capability.get("description")
        or body.get("description")
        or change["title"]
    ).strip()[:1000]
    instructions = str(
        body.get("skill_md")
        or adaptation.get("instructions")
        or proposal.get("instructions")
        or change["body"]
    ).strip()[:30_000]
    if not description or not instructions:
        raise ValueError("reviewed change does not contain usable expert instructions")

    if kind == "skill":
        updated, found = _change_skill(
            roots,
            name=name,
            description=description,
            instructions=instructions,
            evidence_id=evidence_id,
            operation=operation,
        )
        if found:
            return updated
        if operation == "retire":
            raise ValueError(f"reviewed change cannot retire missing Skill {name!r}")
        return _attach_skill(
            updated,
            target_role=target_role,
            skill=SkillBlueprint(
                name=name,
                description=description,
                instructions=instructions,
                evidence_refs=(evidence_id,),
            ),
        )

    updated, found = _change_role(
        roots,
        name=name,
        description=description,
        instructions=instructions,
        evidence_id=evidence_id,
        operation=operation,
    )
    if found:
        return updated
    if operation == "retire":
        raise ValueError(f"reviewed change cannot retire missing Role {name!r}")
    annotations = _new_role_annotations(name, body, proposal, roots, target_role)
    role = RoleBlueprint(
        name=name,
        description=description,
        instructions=instructions,
        tool_requirements=("lookup-evidence",),
        evidence_refs=(evidence_id,),
        annotations=annotations,
    )
    return _attach_role(updated, target_role=target_role, role=role)


def _change_skill(
    roles: tuple[RoleBlueprint, ...],
    *,
    name: str,
    description: str,
    instructions: str,
    evidence_id: str,
    operation: str,
) -> tuple[tuple[RoleBlueprint, ...], bool]:
    found = False
    result: list[RoleBlueprint] = []
    for role in roles:
        children, child_found = _change_skill(
            role.children,
            name=name,
            description=description,
            instructions=instructions,
            evidence_id=evidence_id,
            operation=operation,
        )
        skills: list[SkillBlueprint] = []
        role_found = False
        for skill in role.skills:
            if skill.name != name:
                skills.append(skill)
                continue
            role_found = True
            if operation != "retire":
                skills.append(
                    skill.model_copy(
                        update={
                            "description": description,
                            "instructions": instructions,
                            "evidence_refs": tuple(
                                dict.fromkeys((*skill.evidence_refs, evidence_id))
                            ),
                        }
                    )
                )
        found = found or child_found or role_found
        result.append(role.model_copy(update={"children": children, "skills": tuple(skills)}))
    return tuple(result), found


def _change_role(
    roles: tuple[RoleBlueprint, ...],
    *,
    name: str,
    description: str,
    instructions: str,
    evidence_id: str,
    operation: str,
) -> tuple[tuple[RoleBlueprint, ...], bool]:
    found = False
    result: list[RoleBlueprint] = []
    for role in roles:
        children, child_found = _change_role(
            role.children,
            name=name,
            description=description,
            instructions=instructions,
            evidence_id=evidence_id,
            operation=operation,
        )
        matches = role.name == name or role.annotations.get("oc.profile_name") == name
        found = found or child_found or matches
        if matches and operation == "retire":
            continue
        if matches:
            role = role.model_copy(
                update={
                    "description": description,
                    "instructions": instructions,
                    "evidence_refs": tuple(
                        dict.fromkeys((*role.evidence_refs, evidence_id))
                    ),
                }
            )
        result.append(role.model_copy(update={"children": children}))
    return tuple(result), found


def _attach_skill(
    roots: tuple[RoleBlueprint, ...],
    *,
    target_role: str,
    skill: SkillBlueprint,
) -> tuple[RoleBlueprint, ...]:
    target = target_role.strip()
    if target:
        updated, found = _map_role(
            roots,
            target,
            lambda role: role.model_copy(update={"skills": (*role.skills, skill)}),
        )
        if not found:
            raise ValueError(f"reviewed change target Role {target!r} does not exist")
        return updated
    team = next((role for role in roots if role.name == "team"), None)
    if team is None:
        raise ValueError("base ExpertNet has no team root for an unbound Skill")
    return tuple(
        role.model_copy(update={"skills": (*role.skills, skill)})
        if role is team
        else role
        for role in roots
    )


def _attach_role(
    roots: tuple[RoleBlueprint, ...],
    *,
    target_role: str,
    role: RoleBlueprint,
) -> tuple[RoleBlueprint, ...]:
    target = target_role.strip()
    if target:
        updated, found = _map_role(
            roots,
            target,
            lambda parent: parent.model_copy(update={"children": (*parent.children, role)}),
        )
        if not found:
            raise ValueError(f"reviewed change parent Role {target!r} does not exist")
        return updated
    team = next((item for item in roots if item.name == "team"), None)
    if team is None:
        raise ValueError("base ExpertNet has no team root for a new Role")
    return tuple(
        item.model_copy(update={"children": (*item.children, role)})
        if item is team
        else item
        for item in roots
    )


def _map_role(
    roles: tuple[RoleBlueprint, ...],
    name: str,
    transform: Callable[[RoleBlueprint], RoleBlueprint],
) -> tuple[tuple[RoleBlueprint, ...], bool]:
    found = False
    rows: list[RoleBlueprint] = []
    for role in roles:
        children, child_found = _map_role(role.children, name, transform)
        role = role.model_copy(update={"children": children})
        matches = role.name == name or role.annotations.get("oc.profile_name") == name
        if matches:
            role = transform(role)
        found = found or child_found or matches
        rows.append(role)
    return tuple(rows), found


def _new_role_annotations(
    name: str,
    body: dict[str, Any],
    proposal: dict[str, Any],
    roots: tuple[RoleBlueprint, ...],
    target_role: str,
) -> dict[str, Any]:
    labels = body.get("labels")
    labels = labels if isinstance(labels, dict) else {}
    if labels.get("hand"):
        return {
            "oc.profile_name": name,
            "oc.hand": str(labels["hand"]),
            "oc.project": str(labels.get("project") or "*"),
            "oc.division": str(labels.get("division") or ""),
            "oc.model": str(labels.get("model") or ""),
            "oc.fallback_hands": [],
            "oc.connectors": [],
            "oc.mcp_bindings": [],
            "oc.plugins": [],
            "oc.is_orchestrator": False,
            "oc.compatible_harnesses": [str(labels["hand"])],
        }
    template_name = target_role or str(proposal.get("template_role") or "")
    template = _find_role(roots, template_name) if template_name else None
    return dict(template.annotations) | {"oc.profile_name": name} if template else {}


def _find_role(roles: tuple[RoleBlueprint, ...], name: str) -> RoleBlueprint | None:
    for role in roles:
        if role.name == name or role.annotations.get("oc.profile_name") == name:
            return role
        nested = _find_role(role.children, name)
        if nested is not None:
            return nested
    return None


__all__ = ["BlueprintReviser"]
