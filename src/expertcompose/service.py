"""Stable application facade shared by CLI and Contexture Tools."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from .evaluation import ExpertNetEvaluator, load_observations
from .generator import BuildResult, ContextureGenerator
from .governance import Governance, build_from_workspace
from .ingestion import Ingestor
from .models import (
    Approval,
    EvaluationObservation,
    EvaluationReport,
    EvaluationSuite,
    ExpertBlueprint,
    ReleaseManifest,
    ReleaseStatus,
    ScopeBinding,
    SourceKind,
    SourceRecord,
    stable_id,
    utc_now,
)
from .revisions import BlueprintReviser
from .runtime import canonical_release_selectors, release_surface_selection
from .source_pack import SourcePackImporter
from .synthesis import Composer, SynthesisProvider
from .workspace import Workspace


class ExpertComposeService:
    def __init__(self, root: Path | str) -> None:
        self.workspace = Workspace(root)
        self.ingestor = Ingestor(self.workspace)
        self.composer = Composer(self.workspace)
        self.generator = ContextureGenerator(self.workspace)
        self.evaluator = ExpertNetEvaluator(self.workspace)
        self.governance = Governance(self.workspace)
        self.source_packs = SourcePackImporter(self.workspace, self.ingestor)
        self.reviser = BlueprintReviser(self.workspace, self.ingestor)

    def initialize(self) -> Path:
        self.workspace.initialize()
        return self.workspace.root

    def create_project(self, project_id: str, title: str, objective: str) -> dict[str, str]:
        return self.workspace.create_project(project_id, title, objective)

    def list_projects(self) -> list[dict[str, str]]:
        return self.workspace.list_projects()

    def project_status(self, project_id: str) -> dict[str, object]:
        project = self.workspace.project(project_id)
        sources = self.workspace.list_sources(project_id)
        blueprints = self.workspace.list_blueprints(project_id)
        return {
            "project": project,
            "source_count": len(sources),
            "sources": [item.model_dump(mode="json") for item in sources],
            "blueprint_count": len(blueprints),
            "blueprints": [
                {
                    "blueprint_id": item.blueprint_id,
                    "version": item.version,
                    "status": item.status.value,
                    "sha256": item.canonical_sha256(),
                    "provider": item.provider,
                }
                for item in blueprints
            ],
        }

    def ingest(
        self,
        project_id: str,
        path: Path | str,
        *,
        authorization: str,
        title: str = "",
        license: str = "unknown",
        kind: SourceKind | None = None,
    ) -> tuple[SourceRecord, bool]:
        return self.ingestor.import_path(
            project_id,
            path,
            authorization=authorization,
            title=title,
            license=license,
            kind=kind,
        )

    def compose(
        self,
        project_id: str,
        *,
        provider: SynthesisProvider,
        created_by: str,
    ) -> ExpertBlueprint:
        return self.composer.compose(project_id, provider=provider, created_by=created_by)

    def import_source_pack(
        self,
        project_id: str,
        path: Path | str,
        *,
        authorization: str,
        created_by: str,
        license: str = "unknown",
    ) -> ExpertBlueprint:
        return self.source_packs.import_path(
            project_id,
            path,
            authorization=authorization,
            license=license,
            created_by=created_by,
        )

    def import_source_pack_value(
        self,
        project_id: str,
        value: dict[str, Any],
        *,
        authorization: str,
        created_by: str,
        license: str = "unknown",
    ) -> ExpertBlueprint:
        return self.source_packs.import_value(
            project_id,
            value,
            authorization=authorization,
            license=license,
            created_by=created_by,
        )

    def revise(
        self,
        project_id: str,
        *,
        base_release_id: str,
        change: dict[str, Any],
        authorization: str,
        created_by: str,
    ) -> ExpertBlueprint:
        """Create the next ordinary Blueprint from a reviewed bounded change."""

        return self.reviser.submit(
            project_id,
            base_release_id=base_release_id,
            change=change,
            authorization=authorization,
            created_by=created_by,
        )

    def supersede(self, project_id: str, blueprint_id: str) -> ExpertBlueprint:
        return self.reviser.supersede(project_id, blueprint_id)

    def build(self, project_id: str, blueprint_id: str = "") -> BuildResult:
        return self.generator.build(self.workspace.blueprint(project_id, blueprint_id))

    def suite(self, project_id: str, blueprint_id: str = "") -> EvaluationSuite:
        blueprint = self.workspace.blueprint(project_id, blueprint_id)
        suite = self.evaluator.suite(blueprint)
        path = self.workspace.project_dir(project_id) / "evaluations" / f"{suite.suite_id}.json"
        path.write_text(suite.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return suite

    def observations_template(self, project_id: str, blueprint_id: str = "") -> Path:
        suite = self.suite(project_id, blueprint_id)
        path = (
            self.workspace.project_dir(project_id)
            / "evaluations"
            / (f"{suite.suite_id}-observations.template.json")
        )
        value = {
            "suite_id": suite.suite_id,
            "observations": [
                EvaluationObservation(
                    case_id=case.case_id,
                    passed=False,
                    notes="Replace with a signed or otherwise trusted Host run receipt.",
                ).model_dump(mode="json")
                for case in suite.cases
            ],
        }
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def evaluate(
        self,
        project_id: str,
        blueprint_id: str = "",
        *,
        observations_path: Path | str | None = None,
        require_behavioral: bool = False,
    ) -> EvaluationReport:
        blueprint = self.workspace.blueprint(project_id, blueprint_id)
        build = build_from_workspace(self.workspace, blueprint)
        observations = load_observations(observations_path) if observations_path is not None else ()
        return self.evaluator.evaluate(
            blueprint,
            build,
            observations=observations,
            require_behavioral=require_behavioral,
        )

    def approve(
        self,
        project_id: str,
        blueprint_id: str = "",
        *,
        approved_by: str,
        note: str = "",
    ) -> tuple[ExpertBlueprint, Approval]:
        blueprint = self.workspace.blueprint(project_id, blueprint_id)
        return self.governance.approve(blueprint, approved_by=approved_by, note=note)

    def publish(
        self,
        project_id: str,
        blueprint_id: str = "",
        *,
        published_by: str,
    ) -> ReleaseManifest:
        blueprint = self.workspace.blueprint(project_id, blueprint_id)
        existing = next(
            (
                release
                for release in self.workspace.list_releases(project_id)
                if release.blueprint_id == blueprint.blueprint_id
                and release.status is ReleaseStatus.PUBLISHED
            ),
            None,
        )
        if existing is not None:
            return existing
        # Approval changes workflow state but not the semantic Blueprint digest.
        # Re-render here so the immutable release carries the approved record,
        # rather than the earlier draft bytes used during evaluation.
        build = self.generator.build(blueprint)
        return self.governance.publish(blueprint, build, published_by=published_by)

    def release_catalog(
        self,
        release_id: str,
        *,
        scope_refs: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Return a verified, optionally Scope-selected published Blueprint.

        This is the narrow machine-to-machine read contract. It exposes no
        Workspace path and executes no generated release code.
        """

        release = self.workspace.release(release_id)
        if release.status is not ReleaseStatus.PUBLISHED:
            raise ValueError("only a published ExpertNet release can be consumed")
        blueprint_path = Path(release.artifact_path) / "expert-blueprint.json"
        blueprint = ExpertBlueprint.model_validate_json(
            blueprint_path.read_text(encoding="utf-8")
        )
        if blueprint.blueprint_id != release.blueprint_id:
            raise ValueError("ExpertNet release and Blueprint identity do not match")
        if blueprint.canonical_sha256() != release.blueprint_sha256:
            raise ValueError("ExpertNet release Blueprint digest does not match")

        selectors: tuple[str, ...] = ()
        value = blueprint.model_dump(mode="json")
        if scope_refs:
            selection = release_surface_selection(
                self.workspace, release.release_id, scope_refs
            )
            selectors = tuple(sorted(selection.names or ()))
            if selection.names is not None:
                value["roots"] = _selected_roots(value["roots"], selectors)
        release_value = release.model_dump(mode="json", exclude={"artifact_path"})
        return {
            "release": release_value,
            "scope_refs": list(dict.fromkeys(scope_refs)),
            "role_selectors": list(selectors),
            "catalog_sha256": _blueprint_value_sha256(value),
            "blueprint": value,
        }

    def scope_catalog(self, scope_ref: str) -> dict[str, Any]:
        """Resolve one Scope only when it has exactly one enabled binding."""

        bindings = self.workspace.list_scope_bindings(scope_ref=scope_ref, enabled=True)
        if not bindings:
            raise PermissionError("no enabled ScopeBinding authorizes this Scope")
        if len(bindings) != 1:
            raise ValueError(
                "Scope has multiple enabled bindings; reconcile it before serving a catalog"
            )
        return self.release_catalog(
            bindings[0].release_id,
            scope_refs=(scope_ref,),
        )

    def create_scope_binding(
        self,
        *,
        scope_ref: str,
        release_id: str,
        role_selectors: tuple[str, ...] = (),
        created_by: str,
    ) -> ScopeBinding:
        release = self.workspace.release(release_id)
        selectors = canonical_release_selectors(release, role_selectors)
        binding_id = stable_id("bind", scope_ref, release_id, *selectors)
        try:
            return self.workspace.scope_binding(binding_id)
        except FileNotFoundError:
            pass
        now = utc_now()
        binding = ScopeBinding(
            binding_id=binding_id,
            scope_ref=scope_ref,
            release_id=release_id,
            role_selectors=selectors,
            created_at=now,
            updated_at=now,
            created_by=created_by,
        )
        self.workspace.save_scope_binding(binding)
        return binding

    def list_scope_bindings(
        self,
        *,
        scope_ref: str = "",
        include_disabled: bool = False,
    ) -> list[ScopeBinding]:
        return self.workspace.list_scope_bindings(
            scope_ref=scope_ref,
            enabled=None if include_disabled else True,
        )

    def set_scope_binding_enabled(
        self,
        binding_id: str,
        *,
        enabled: bool,
        expected_revision: int,
    ) -> ScopeBinding:
        current = self.workspace.scope_binding(binding_id)
        if current.revision != expected_revision:
            raise ValueError("ScopeBinding revision conflict")
        if current.enabled is enabled:
            return current
        updated = current.model_copy(
            update={
                "enabled": enabled,
                "revision": current.revision + 1,
                "updated_at": utc_now(),
            }
        )
        self.workspace.save_scope_binding(updated, expected_revision=expected_revision)
        return updated


def _selected_roots(roots: Any, selectors: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(roots, list):
        raise ValueError("ExpertNet Blueprint roots must be a list")
    selected: list[dict[str, Any]] = []
    for root in cast(list[Any], roots):
        if not isinstance(root, dict) or not isinstance(root.get("name"), str):
            raise ValueError("ExpertNet Blueprint contains an invalid Role")
        root_value = cast(dict[str, Any], root)
        projected = _selected_role(root_value, str(root_value["name"]), selectors)
        if projected is not None:
            selected.append(projected)
    return selected


def _blueprint_value_sha256(value: dict[str, Any]) -> str:
    semantic = json.loads(json.dumps(value))
    semantic.pop("status", None)
    semantic.pop("created_at", None)
    for binding in semantic.get("tool_bindings", []):
        if isinstance(binding, dict):
            binding.pop("reviewed_at", None)
    raw = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _selected_role(
    role: dict[str, Any],
    path: str,
    selectors: tuple[str, ...],
) -> dict[str, Any] | None:
    fully_selected = any(
        path == selector or path.startswith(selector + "/") for selector in selectors
    )
    selected_below = any(selector.startswith(path + "/") for selector in selectors)
    if not fully_selected and not selected_below:
        return None
    value = dict(role)
    if fully_selected:
        return value

    children = role.get("children", [])
    if not isinstance(children, list):
        raise ValueError(f"ExpertNet Role {path!r} has invalid children")
    projected_children: list[dict[str, Any]] = []
    for child in cast(list[Any], children):
        if not isinstance(child, dict) or not isinstance(child.get("name"), str):
            raise ValueError(f"ExpertNet Role {path!r} contains an invalid child")
        child_value = cast(dict[str, Any], child)
        projected = _selected_role(
            child_value, f"{path}/{child_value['name']}", selectors
        )
        if projected is not None:
            projected_children.append(projected)
    value["children"] = projected_children

    skills = role.get("skills", [])
    if not isinstance(skills, list):
        raise ValueError(f"ExpertNet Role {path!r} has invalid Skills")
    value["skills"] = [
        skill
        for skill in cast(list[Any], skills)
        if isinstance(skill, dict)
        and isinstance(skill.get("name"), str)
        and f"{path}/{skill['name']}" in selectors
    ]
    return value


__all__ = ["ExpertComposeService"]
