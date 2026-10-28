"""Deterministic import of reviewed expert-team source packs.

The pack is untrusted source data. Its bounded schema is converted to the same
draft Blueprint lifecycle as every other provider and cannot publish itself.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, JsonValue, model_validator

from .ingestion import Ingestor, redact
from .models import (
    Evidence,
    EvidenceKind,
    ExpertBlueprint,
    Record,
    RoleBlueprint,
    SkillBlueprint,
    SourceKind,
    SourceRecord,
    TaskSpec,
    ToolBinding,
    ToolRequirement,
    require_name,
    stable_id,
    utc_now,
)
from .workspace import Workspace


class PackMessage(Record):
    role: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=30_000)


class PackSkill(Record):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    description: str = Field(min_length=1, max_length=1000)
    instructions: str = Field(min_length=1, max_length=30_000)
    uses: tuple[str, ...] = Field(default=(), max_length=200)

    @model_validator(mode="after")
    def valid_uses(self) -> Self:
        if len(self.uses) != len(set(self.uses)):
            raise ValueError(f"source-pack Skill {self.name!r} has duplicate uses refs")
        for ref in self.uses:
            if not re.fullmatch(
                r"[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)+", ref
            ):
                raise ValueError(
                    f"source-pack Skill {self.name!r} has invalid uses ref {ref!r}"
                )
        return self


class PackRole(Record):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    description: str = Field(min_length=1, max_length=1000)
    instructions: str = Field(min_length=1, max_length=30_000)
    path: tuple[str, ...] = Field(max_length=8)
    skills: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    annotations: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_path(self) -> Self:
        for segment in self.path:
            if require_name(segment) != segment:
                raise ValueError("source-pack Role path segments must be kebab-case names")
        return self


class TeamSourcePack(Record):
    format: Literal["expertcompose.source-pack.v1", "expertcompose.source-pack.v2"]
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    title: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1, max_length=4000)
    roles: tuple[PackRole, ...] = Field(min_length=1, max_length=500)
    skills: tuple[PackSkill, ...] = Field(default=(), max_length=1000)
    messages: tuple[PackMessage, ...] = Field(min_length=1, max_length=1500)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def coherent(self) -> Self:
        role_names = [item.name for item in self.roles]
        skill_names = [item.name for item in self.skills]
        if len(role_names) != len(set(role_names)):
            raise ValueError("source-pack Role names must be unique")
        if len(skill_names) != len(set(skill_names)):
            raise ValueError("source-pack Skill names must be unique")
        known_skills = set(skill_names)
        if self.format == "expertcompose.source-pack.v1" and any(
            skill.uses for skill in self.skills
        ):
            raise ValueError("source-pack v1 cannot declare Skill uses; use v2")
        for role in self.roles:
            unknown = set(role.skills) - known_skills
            if unknown:
                raise ValueError(
                    f"source-pack Role {role.name!r} references unknown Skills: "
                    + ", ".join(sorted(unknown))
                )
            if len(role.skills) != len(set(role.skills)) or len(role.tools) != len(
                set(role.tools)
            ):
                raise ValueError(f"source-pack Role {role.name!r} has duplicate members")
        expected = tuple(
            [
                PackMessage(role=f"role:{item.name}", content=item.instructions)
                for item in self.roles
            ]
            + [
                PackMessage(role=f"skill:{item.name}", content=item.instructions)
                for item in self.skills
            ]
        )
        if self.messages != expected:
            raise ValueError("source-pack messages must exactly mirror Role and Skill instructions")
        if self.content_sha256 != source_pack_digest(self):
            raise ValueError("source-pack content_sha256 does not match its contents")
        return self


def source_pack_digest(pack: TeamSourcePack | dict[str, object]) -> str:
    if isinstance(pack, TeamSourcePack):
        value = pack.model_dump(mode="json", exclude={"content_sha256"})
        if pack.format == "expertcompose.source-pack.v1":
            for skill in value["skills"]:
                skill.pop("uses", None)
    else:
        value = dict(pack)
        value.pop("content_sha256", None)
        if value.get("format") == "expertcompose.source-pack.v1":
            skills = value.get("skills")
            if isinstance(skills, list):
                value["skills"] = [
                    {key: item for key, item in skill.items() if key != "uses"}
                    if isinstance(skill, dict) and not skill.get("uses")
                    else skill
                    for skill in skills
                ]
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class SourcePackImporter:
    def __init__(self, workspace: Workspace, ingestor: Ingestor) -> None:
        self.workspace = workspace
        self.ingestor = ingestor

    def import_path(
        self,
        project_id: str,
        path: Path | str,
        *,
        authorization: str,
        license: str,
        created_by: str,
    ) -> ExpertBlueprint:
        source_path = Path(path).expanduser().resolve()
        try:
            value = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"source pack is not valid UTF-8 JSON: {error}") from error
        pack = TeamSourcePack.model_validate(value)
        source, _created = self.ingestor.import_path(
            project_id,
            source_path,
            authorization=authorization,
            license=license,
            title=pack.title,
        )
        return self._build(project_id, pack, source, created_by=created_by)

    def import_value(
        self,
        project_id: str,
        value: dict[str, Any],
        *,
        authorization: str,
        license: str,
        created_by: str,
    ) -> ExpertBlueprint:
        """Import a bounded JSON pack received through a trusted host."""

        pack = TeamSourcePack.model_validate(value)
        raw = (
            json.dumps(
                pack.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        source, _created = self.ingestor.import_bytes(
            project_id,
            raw,
            kind=SourceKind.JSON,
            origin=f"api://source-pack/{pack.content_sha256}",
            authorization=authorization,
            license=license,
            title=pack.title,
        )
        return self._build(project_id, pack, source, created_by=created_by)

    def _build(
        self,
        project_id: str,
        pack: TeamSourcePack,
        source: SourceRecord,
        *,
        created_by: str,
    ) -> ExpertBlueprint:
        units = self.workspace.source_units(project_id, source.source_id)
        if len(units) != len(pack.messages):
            raise ValueError("normalized source-pack message count changed during ingestion")

        evidence: list[Evidence] = []
        evidence_by_role: dict[str, str] = {}
        evidence_by_skill: dict[str, str] = {}
        for index, (message, unit) in enumerate(zip(pack.messages, units, strict=True), 1):
            kind, name = message.role.split(":", 1)
            evidence_id = stable_id("ev", source.source_id, str(index), unit.sha256)
            description = (
                next(item.description for item in pack.roles if item.name == name)
                if kind == "role"
                else next(item.description for item in pack.skills if item.name == name)
            )
            summary, _redactions = redact(description)
            evidence.append(
                Evidence(
                    evidence_id=evidence_id,
                    source_id=source.source_id,
                    locator=unit.locator,
                    kind=EvidenceKind.PROCEDURE,
                    summary=summary,
                    excerpt=unit.text[:4000],
                    sha256=unit.sha256,
                    confidence=1.0,
                    tags=("source-pack", kind, name),
                )
            )
            target = evidence_by_role if kind == "role" else evidence_by_skill
            target[name] = evidence_id

        skill_map = {item.name: item for item in pack.skills}
        tool_names = tuple(sorted({name for role in pack.roles for name in role.tools}))
        all_evidence = tuple(item.evidence_id for item in evidence)
        lookup_schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        }
        requirements = [
            ToolRequirement(
                name="lookup-evidence",
                description="Search bounded release evidence and return exact locators.",
                reason="Imported expert procedures must remain traceable to their source pack.",
                required=True,
                input_schema=lookup_schema,
                evidence_refs=all_evidence,
            )
        ]
        requirements.extend(
            ToolRequirement(
                name=require_name(name),
                description=f"Host-provided capability required by imported Roles: {name}.",
                reason="Declared by the reviewed source pack; binding remains a host decision.",
                required=False,
                evidence_refs=all_evidence,
            )
            for name in tool_names
            if require_name(name) != "lookup-evidence"
        )

        def role(item: PackRole) -> RoleBlueprint:
            profile_evidence = evidence_by_role[item.name]
            skills = tuple(
                SkillBlueprint(
                    name=name,
                    description=redact(skill_map[name].description)[0],
                    instructions=_unit_content(
                        units[len(pack.roles) + list(skill_map).index(name)].text
                    ),
                    uses=skill_map[name].uses,
                    evidence_refs=(evidence_by_skill[name],),
                )
                for name in item.skills
            )
            return RoleBlueprint(
                name=item.name,
                description=redact(item.description)[0],
                instructions=_unit_content(units[list(pack.roles).index(item)].text),
                skills=skills,
                tool_requirements=tuple(
                    dict.fromkeys(("lookup-evidence", *(require_name(name) for name in item.tools)))
                ),
                evidence_refs=(profile_evidence,),
                annotations=item.annotations,
            )

        tree = _RoleGroup()
        for item in pack.roles:
            node = tree
            for segment in item.path:
                node = node.groups.setdefault(segment, _RoleGroup())
            node.roles.append(role(item))
        children = _group_children(tree)
        version = self.workspace.next_blueprint_version(project_id)
        digest = source_pack_digest(pack)
        task = TaskSpec(
            task_id=stable_id("task", source.source_id, "use-imported-team", length=20),
            name="use-imported-team",
            description="Select an imported Role and apply its reviewed procedure.",
            success_criteria=(
                "The selected Role follows its imported instructions.",
                "Material conclusions retain source evidence references.",
            ),
            evidence_refs=all_evidence,
        )
        blueprint = ExpertBlueprint(
            blueprint_id=stable_id("bp", project_id, str(version), digest),
            project_id=project_id,
            name=require_name(project_id),
            title=pack.title,
            objective=pack.objective,
            version=version,
            roots=(
                RoleBlueprint(
                    name="team",
                    description="Imported expert team.",
                    instructions=(
                        "Select the narrowest Role that owns the requested responsibility and "
                        "keep conclusions traceable to imported evidence."
                    ),
                    children=children,
                    tool_requirements=("lookup-evidence",),
                    evidence_refs=all_evidence,
                ),
            ),
            source_ids=(source.source_id,),
            tasks=(task,),
            tool_requirements=tuple(requirements),
            tool_bindings=(
                ToolBinding(
                    requirement="lookup-evidence",
                    binding_kind="builtin",
                    target="expertcompose.generated:EvidenceLookup",
                    schema_sha256=hashlib.sha256(
                        json.dumps(lookup_schema, sort_keys=True).encode()
                    ).hexdigest(),
                    reviewed_by="expertcompose-framework",
                    reviewed_at=utc_now(),
                ),
            ),
            created_at=utc_now(),
            created_by=created_by,
            provider="source-pack-v1",
        )
        self.workspace.save_evidence(project_id, evidence)
        self.workspace.save_blueprint(blueprint)
        return blueprint


def _unit_content(text: str) -> str:
    _header, separator, content = text.partition("\n")
    return content if separator else text


@dataclass(slots=True)
class _RoleGroup:
    groups: dict[str, _RoleGroup] = field(default_factory=dict)
    roles: list[RoleBlueprint] = field(default_factory=list)


def _group_children(group: _RoleGroup) -> tuple[RoleBlueprint, ...]:
    rows: list[RoleBlueprint] = []
    for name, child in group.groups.items():
        children = _group_children(child)
        evidence_refs = tuple(
            dict.fromkeys(ref for item in children for ref in item.evidence_refs)
        )
        rows.append(
            RoleBlueprint(
                name=name,
                description=f"Responsibility group for {name} experts.",
                instructions=(
                    "Select the child Role whose declared responsibility matches the task."
                ),
                children=children,
                evidence_refs=evidence_refs,
            )
        )
    rows.extend(group.roles)
    return tuple(rows)


__all__ = [
    "PackMessage",
    "PackRole",
    "PackSkill",
    "SourcePackImporter",
    "TeamSourcePack",
    "source_pack_digest",
]
