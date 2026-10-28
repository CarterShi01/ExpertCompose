"""Explicit approval and immutable publication gates."""

from __future__ import annotations

import shutil

from .errors import InvalidTransitionError, PublicationBlockedError
from .generator import BuildResult
from .models import (
    Approval,
    BlueprintStatus,
    ExpertBlueprint,
    ReleaseManifest,
    ReleaseStatus,
    stable_id,
    utc_now,
)
from .workspace import Workspace


class Governance:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def approve(
        self,
        blueprint: ExpertBlueprint,
        *,
        approved_by: str,
        note: str = "",
    ) -> tuple[ExpertBlueprint, Approval]:
        report = self.workspace.evaluation(blueprint.blueprint_id)
        digest = blueprint.canonical_sha256()
        if report.status != "passed":
            raise InvalidTransitionError("a failed evaluation cannot be approved")
        if report.blueprint_sha256 != digest:
            raise InvalidTransitionError("evaluation does not cover the current Blueprint bytes")
        if blueprint.status not in {BlueprintStatus.EVALUATED, BlueprintStatus.APPROVED}:
            raise InvalidTransitionError(
                f"Blueprint status {blueprint.status.value!r} cannot move to approved"
            )
        if blueprint.status is BlueprintStatus.APPROVED:
            return blueprint, self.workspace.approval(blueprint.blueprint_id)
        approval = Approval(
            blueprint_id=blueprint.blueprint_id,
            blueprint_sha256=digest,
            report_id=report.report_id,
            approved_by=approved_by,
            approved_at=utc_now(),
            note=note,
        )
        approved = blueprint.model_copy(update={"status": BlueprintStatus.APPROVED})
        self.workspace.save_approval(blueprint.project_id, approval)
        self.workspace.save_blueprint(approved)
        return approved, approval

    def publish(
        self,
        blueprint: ExpertBlueprint,
        build: BuildResult,
        *,
        published_by: str,
    ) -> ReleaseManifest:
        if blueprint.status is not BlueprintStatus.APPROVED:
            raise PublicationBlockedError("only an approved Blueprint can be published")
        approval = self.workspace.approval(blueprint.blueprint_id)
        digest = blueprint.canonical_sha256()
        if approval.blueprint_sha256 != digest:
            raise PublicationBlockedError("approval does not cover the current Blueprint bytes")
        report = self.workspace.evaluation(blueprint.blueprint_id, approval.report_id)
        if report.status != "passed" or report.blueprint_sha256 != digest:
            raise PublicationBlockedError(
                "publication requires a passing evaluation of exact bytes"
            )
        if build.blueprint_id != blueprint.blueprint_id:
            raise PublicationBlockedError("build was produced from a different Blueprint")
        if build.unbound_required_tools:
            raise PublicationBlockedError(
                "required Tool bindings are missing: " + ", ".join(build.unbound_required_tools)
            )
        release_id = stable_id(
            "rel", blueprint.project_id, str(blueprint.version), digest, build.artifact_sha256
        )
        release_root = (
            self.workspace.project_dir(blueprint.project_id)
            / "releases"
            / (f"v{blueprint.version:04d}-{release_id}")
        )
        artifact = release_root / "artifact"
        if artifact.exists():
            raise PublicationBlockedError(f"immutable release already exists at {artifact}")
        release_root.mkdir(parents=True, exist_ok=False)
        try:
            shutil.copytree(build.path, artifact)
        except Exception:
            shutil.rmtree(release_root, ignore_errors=True)
            raise
        manifest = ReleaseManifest(
            release_id=release_id,
            project_id=blueprint.project_id,
            blueprint_id=blueprint.blueprint_id,
            blueprint_sha256=digest,
            report_id=report.report_id,
            version=blueprint.version,
            status=ReleaseStatus.PUBLISHED,
            artifact_path=str(artifact),
            artifact_sha256=build.artifact_sha256,
            published_at=utc_now(),
            published_by=published_by,
        )
        self.workspace.save_release(manifest)
        return manifest


def build_from_workspace(workspace: Workspace, blueprint: ExpertBlueprint) -> BuildResult:
    """Rehydrate the exact generated build for governance commands."""

    build_dir = (
        workspace.project_dir(blueprint.project_id)
        / "builds"
        / (f"v{blueprint.version:04d}-{blueprint.blueprint_id}")
    )
    manifest_path = build_dir / "build-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("build the Blueprint before evaluating or publishing it")
    import json

    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    return BuildResult(
        project_id=blueprint.project_id,
        blueprint_id=blueprint.blueprint_id,
        path=build_dir,
        package=str(value["package"]),
        artifact_sha256=str(value["artifact_sha256"]),
        files=tuple(str(item) for item in value["files"]),
        unbound_required_tools=tuple(str(item) for item in value["unbound_required_tools"]),
    )


__all__ = ["Governance", "build_from_workspace"]
