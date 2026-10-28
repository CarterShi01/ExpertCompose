from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from contexture.server import compile_application

from expertcompose.errors import PublicationBlockedError
from expertcompose.models import BlueprintStatus, EvaluationObservation, ReleaseStatus
from expertcompose.service import ExpertComposeService
from expertcompose.synthesis import HeuristicProvider


def _compose(service: ExpertComposeService, source_file: Path) -> tuple[str, str]:
    source, _ = service.ingest(
        "literature-review", source_file, authorization="Repository test source"
    )
    blueprint = service.compose(
        "literature-review", provider=HeuristicProvider(), created_by="pytest"
    )
    return source.source_id, blueprint.blueprint_id


def _load_generated(build_path: Path, package: str) -> ModuleType:
    package_dir = build_path / "src" / package
    alias = "_expertcompose_test_generated"
    spec = importlib.util.spec_from_file_location(
        alias,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_complete_offline_lifecycle(service: ExpertComposeService, source_file: Path) -> None:
    source_id, blueprint_id = _compose(service, source_file)
    draft = service.workspace.blueprint("literature-review", blueprint_id)
    build = service.build("literature-review", blueprint_id)
    assert not build.unbound_required_tools
    assert (build.path / "build-manifest.json").is_file()
    runner = build.path / "src" / build.package / "__main__.py"
    assert "HeaderSurfaceSelector" in runner.read_text(encoding="utf-8")

    generated = _load_generated(build.path, build.package)
    compiled = compile_application(generated.app)
    refs = {ref for ref, _node in compiled.index.walk()}
    assert any(ref.endswith("/lookup-evidence") for ref in refs)

    app_module = cast(Any, sys.modules[generated.__name__ + ".app"])
    tool_class = app_module.EvidenceLookup
    result = await tool_class().invoke("contradictory evidence")
    assert result["count"] >= 1
    assert result["results"][0]["source_id"] == source_id

    suite = service.suite("literature-review", blueprint_id)
    failed = service.evaluate("literature-review", blueprint_id, require_behavioral=True)
    assert failed.status == "failed"
    observations_path = service.workspace.project_dir("literature-review") / "receipts.json"
    observations_path.write_text(
        json.dumps(
            {
                "observations": [
                    EvaluationObservation(case_id=case.case_id, passed=True).model_dump(mode="json")
                    for case in suite.cases
                ]
            }
        ),
        encoding="utf-8",
    )
    report = service.evaluate(
        "literature-review",
        blueprint_id,
        observations_path=observations_path,
        require_behavioral=True,
    )
    assert report.status == "passed"
    evaluated = service.workspace.blueprint("literature-review", blueprint_id)
    assert evaluated.status is BlueprintStatus.EVALUATED
    assert evaluated.canonical_sha256() == draft.canonical_sha256()

    approved, approval = service.approve(
        "literature-review", blueprint_id, approved_by="domain-reviewer"
    )
    assert approved.status is BlueprintStatus.APPROVED
    assert approval.report_id == report.report_id
    release = service.publish("literature-review", blueprint_id, published_by="release-manager")
    assert release.status is ReleaseStatus.PUBLISHED
    assert Path(release.artifact_path).is_dir()
    with pytest.raises(PublicationBlockedError, match="already exists"):
        service.publish("literature-review", blueprint_id, published_by="release-manager")

    for name in list(sys.modules):
        if name == generated.__name__ or name.startswith(generated.__name__ + "."):
            sys.modules.pop(name, None)


def test_publish_before_approval_is_refused(
    service: ExpertComposeService, source_file: Path
) -> None:
    _, blueprint_id = _compose(service, source_file)
    service.build("literature-review", blueprint_id)
    with pytest.raises(PublicationBlockedError, match="approved"):
        service.publish("literature-review", blueprint_id, published_by="release-manager")
