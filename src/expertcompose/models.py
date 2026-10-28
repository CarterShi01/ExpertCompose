"""Versioned intermediate representation for evidence and ExpertNets.

The IR is intentionally independent of Contexture. Contexture is one validated
target runtime; persisted product state must remain inspectable without importing
or executing generated declarations.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

NAME_PATTERN = r"^[a-z][a-z0-9-]{0,63}$"
_NAME = re.compile(NAME_PATTERN)


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for persisted records."""

    return datetime.now(UTC)


class Record(BaseModel):
    """Strict immutable value used in content-addressed product records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceKind(StrEnum):
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    PAPER = "paper"
    SESSION = "session"
    JSON = "json"
    JSONL = "jsonl"


class SourceStatus(StrEnum):
    IMPORTED = "imported"
    REJECTED = "rejected"


class BlueprintStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    EVALUATED = "evaluated"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class ReleaseStatus(StrEnum):
    STAGED = "staged"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class EvidenceKind(StrEnum):
    FACT = "fact"
    PROCEDURE = "procedure"
    CONSTRAINT = "constraint"
    EXAMPLE = "example"
    FAILURE = "failure"
    DECISION = "decision"


class SourceLocator(Record):
    """Stable location within normalized source content."""

    unit: Literal["line", "page", "message", "chunk"]
    start: int = Field(ge=1)
    end: int = Field(ge=1)
    label: str = Field(default="", max_length=240)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end < self.start:
            raise ValueError("source locator end must be greater than or equal to start")
        return self


class SourceRecord(Record):
    """One imported, immutable source with consent and provenance metadata."""

    source_id: str = Field(pattern=r"^src_[a-f0-9]{24}$")
    project_id: str = Field(pattern=NAME_PATTERN)
    kind: SourceKind
    title: str = Field(min_length=1, max_length=300)
    origin: str = Field(min_length=1, max_length=2000)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: str = Field(min_length=1, max_length=120)
    byte_count: int = Field(ge=0)
    imported_at: datetime
    authorization: str = Field(min_length=1, max_length=1000)
    license: str = Field(default="unknown", max_length=240)
    status: SourceStatus = SourceStatus.IMPORTED
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedUnit(Record):
    """Bounded source unit used for synthesis; raw bytes remain outside prompts."""

    source_id: str = Field(pattern=r"^src_[a-f0-9]{24}$")
    locator: SourceLocator
    text: str = Field(min_length=1, max_length=20_000)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    redactions: int = Field(default=0, ge=0)


class Evidence(Record):
    """A reviewable assertion derived from an exact source location."""

    evidence_id: str = Field(pattern=r"^ev_[a-f0-9]{24}$")
    source_id: str = Field(pattern=r"^src_[a-f0-9]{24}$")
    locator: SourceLocator
    kind: EvidenceKind
    summary: str = Field(min_length=1, max_length=2000)
    excerpt: str = Field(min_length=1, max_length=4000)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    confidence: float = Field(default=0.7, ge=0, le=1)
    tags: tuple[str, ...] = ()


class Claim(Record):
    claim_id: str = Field(pattern=r"^claim_[a-f0-9]{20}$")
    statement: str = Field(min_length=1, max_length=4000)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    confidence: float = Field(default=0.7, ge=0, le=1)
    conflicts_with: tuple[str, ...] = ()


class Procedure(Record):
    procedure_id: str = Field(pattern=r"^proc_[a-f0-9]{20}$")
    name: str = Field(pattern=NAME_PATTERN)
    goal: str = Field(min_length=1, max_length=1000)
    steps: tuple[str, ...] = Field(min_length=1, max_length=30)
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class TaskSpec(Record):
    task_id: str = Field(pattern=r"^task_[a-f0-9]{20}$")
    name: str = Field(pattern=NAME_PATTERN)
    description: str = Field(min_length=1, max_length=2000)
    success_criteria: tuple[str, ...] = Field(min_length=1)
    inputs: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class SkillBlueprint(Record):
    name: str = Field(pattern=NAME_PATTERN)
    description: str = Field(min_length=1, max_length=1000)
    instructions: str = Field(min_length=1, max_length=30_000)
    uses: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class ToolRequirement(Record):
    """Desired deterministic capability; this record is not executable code."""

    name: str = Field(pattern=NAME_PATTERN)
    description: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=2000)
    read_only: bool = True
    required: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class ToolBinding(Record):
    requirement: str = Field(pattern=NAME_PATTERN)
    binding_kind: Literal["builtin", "python", "mcp"]
    target: str = Field(min_length=1, max_length=1000)
    schema_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed_by: str = Field(min_length=1, max_length=200)
    reviewed_at: datetime


class RoleBlueprint(Record):
    name: str = Field(pattern=NAME_PATTERN)
    description: str = Field(min_length=1, max_length=1000)
    instructions: str = Field(min_length=1, max_length=30_000)
    children: tuple[RoleBlueprint, ...] = ()
    skills: tuple[SkillBlueprint, ...] = ()
    tool_requirements: tuple[str, ...] = ()
    uses: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_members(self) -> Self:
        member_names = [item.name for item in self.children]
        member_names.extend(item.name for item in self.skills)
        member_names.extend(self.tool_requirements)
        if len(member_names) != len(set(member_names)):
            raise ValueError(f"role {self.name!r} contains duplicate member names")
        return self


class ExpertBlueprint(Record):
    """Complete, source-grounded description of one ExpertNet candidate."""

    schema_version: Literal[1] = 1
    blueprint_id: str = Field(pattern=r"^bp_[a-f0-9]{24}$")
    project_id: str = Field(pattern=NAME_PATTERN)
    name: str = Field(pattern=NAME_PATTERN)
    title: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1, max_length=4000)
    version: int = Field(ge=1)
    status: BlueprintStatus = BlueprintStatus.DRAFT
    roots: tuple[RoleBlueprint, ...] = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)
    claims: tuple[Claim, ...] = ()
    procedures: tuple[Procedure, ...] = ()
    tasks: tuple[TaskSpec, ...] = Field(min_length=1)
    tool_requirements: tuple[ToolRequirement, ...] = ()
    tool_bindings: tuple[ToolBinding, ...] = ()
    created_at: datetime
    created_by: str = Field(min_length=1, max_length=200)
    provider: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def coherent_graph(self) -> Self:
        root_names = [root.name for root in self.roots]
        if len(root_names) != len(set(root_names)):
            raise ValueError("blueprint root names must be unique")
        requirements = {item.name for item in self.tool_requirements}
        bindings = [item.requirement for item in self.tool_bindings]
        if not set(bindings).issubset(requirements):
            raise ValueError("a Tool binding names an undeclared requirement")
        if len(bindings) != len(set(bindings)):
            raise ValueError("a Tool requirement has more than one binding")
        return self

    def canonical_sha256(self) -> str:
        """Digest semantic contents while excluding workflow state and timestamps."""

        value = self.model_dump(mode="json", exclude={"status", "created_at"})
        for binding in value.get("tool_bindings", []):
            if isinstance(binding, dict):
                binding.pop("reviewed_at", None)
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


class EvaluationCase(Record):
    case_id: str = Field(pattern=r"^case_[a-f0-9]{20}$")
    task_ref: str = Field(pattern=r"^task_[a-f0-9]{20}$")
    prompt: str = Field(min_length=1, max_length=10_000)
    rubric: tuple[str, ...] = Field(min_length=1)
    held_out: bool = True


class EvaluationSuite(Record):
    suite_id: str = Field(pattern=r"^suite_[a-f0-9]{20}$")
    blueprint_id: str = Field(pattern=r"^bp_[a-f0-9]{24}$")
    cases: tuple[EvaluationCase, ...] = Field(min_length=1)
    created_at: datetime


class EvaluationObservation(Record):
    """Neutral host receipt; ExpertCompose does not prescribe an agent runner."""

    case_id: str = Field(pattern=r"^case_[a-f0-9]{20}$")
    passed: bool
    response: str = Field(default="", max_length=50_000)
    opened_refs: tuple[str, ...] = ()
    invoked_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    metrics: dict[str, float] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=4000)


class CheckResult(Record):
    check_id: str = Field(min_length=1, max_length=120)
    status: Literal["passed", "warning", "failed", "skipped"]
    summary: str = Field(min_length=1, max_length=4000)
    metric: float | None = None
    evidence_refs: tuple[str, ...] = ()


class EvaluationReport(Record):
    report_id: str = Field(pattern=r"^eval_[a-f0-9]{24}$")
    blueprint_id: str = Field(pattern=r"^bp_[a-f0-9]{24}$")
    blueprint_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["passed", "failed"]
    checks: tuple[CheckResult, ...] = Field(min_length=1)
    created_at: datetime
    evaluator: str = Field(min_length=1, max_length=300)


class Approval(Record):
    blueprint_id: str = Field(pattern=r"^bp_[a-f0-9]{24}$")
    blueprint_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_id: str = Field(pattern=r"^eval_[a-f0-9]{24}$")
    approved_by: str = Field(min_length=1, max_length=200)
    approved_at: datetime
    note: str = Field(default="", max_length=4000)


class ReleaseManifest(Record):
    schema_version: Literal[1] = 1
    release_id: str = Field(pattern=r"^rel_[a-f0-9]{24}$")
    project_id: str = Field(pattern=NAME_PATTERN)
    blueprint_id: str = Field(pattern=r"^bp_[a-f0-9]{24}$")
    blueprint_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    report_id: str = Field(pattern=r"^eval_[a-f0-9]{24}$")
    version: int = Field(ge=1)
    status: ReleaseStatus
    artifact_path: str = Field(min_length=1, max_length=2000)
    artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    published_at: datetime | None = None
    published_by: str | None = Field(default=None, max_length=200)


def stable_id(prefix: str, *parts: str, length: int = 24) -> str:
    """Create a deterministic identifier for immutable content."""

    digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()[:length]
    return f"{prefix}_{digest}"


def require_name(value: str) -> str:
    """Normalize and validate a public ExpertNet path segment."""

    normalized = value.strip().lower().replace("_", "-").replace(" ", "-")
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not _NAME.fullmatch(normalized):
        raise ValueError(f"{value!r} cannot be normalized to a valid kebab-case name")
    return normalized


__all__ = [
    "Approval",
    "BlueprintStatus",
    "CheckResult",
    "Claim",
    "EvaluationCase",
    "EvaluationObservation",
    "EvaluationReport",
    "EvaluationSuite",
    "Evidence",
    "EvidenceKind",
    "ExpertBlueprint",
    "NormalizedUnit",
    "Procedure",
    "ReleaseManifest",
    "ReleaseStatus",
    "RoleBlueprint",
    "SkillBlueprint",
    "SourceKind",
    "SourceLocator",
    "SourceRecord",
    "SourceStatus",
    "TaskSpec",
    "ToolBinding",
    "ToolRequirement",
    "require_name",
    "stable_id",
    "utc_now",
]
