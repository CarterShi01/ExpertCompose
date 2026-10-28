"""Stable application facade shared by CLI and Contexture Tools."""

from __future__ import annotations

import json
from pathlib import Path

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
    SourceKind,
    SourceRecord,
)
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
        build = build_from_workspace(self.workspace, blueprint)
        return self.governance.publish(blueprint, build, published_by=published_by)


__all__ = ["ExpertComposeService"]
