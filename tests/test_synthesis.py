from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from expertcompose.errors import SynthesisError
from expertcompose.models import EvidenceKind, NormalizedUnit, SourceRecord
from expertcompose.service import ExpertComposeService
from expertcompose.synthesis import (
    CompositionDraft,
    EvidenceDraft,
    HeuristicProvider,
    RoleDraft,
    TaskDraft,
)


class InventingProvider:
    name = "inventing-test-provider"

    def compose(
        self,
        project: Mapping[str, Any],
        sources: tuple[SourceRecord, ...],
        units: tuple[NormalizedUnit, ...],
    ) -> CompositionDraft:
        return CompositionDraft(
            title="Invented",
            evidence=[
                EvidenceDraft(
                    key="e1",
                    unit_sha256="f" * 64,
                    kind=EvidenceKind.FACT,
                    summary="Invented evidence",
                    excerpt="Invented evidence",
                )
            ],
            tasks=[
                TaskDraft(
                    name="test-task",
                    description="Test",
                    success_criteria=["Grounded"],
                    evidence_keys=["e1"],
                )
            ],
            roots=[
                RoleDraft(
                    name="test-role",
                    description="Test",
                    instructions="Test from evidence.",
                    evidence_keys=["e1"],
                )
            ],
        )


def test_heuristic_blueprint_is_grounded(service: ExpertComposeService, source_file: Path) -> None:
    service.ingest("literature-review", source_file, authorization="Repository test source")
    blueprint = service.compose(
        "literature-review", provider=HeuristicProvider(), created_by="pytest"
    )
    evidence = service.workspace.load_evidence("literature-review")
    assert blueprint.provider == "heuristic-v1"
    assert blueprint.roots[0].children
    assert {item["evidence_id"] for item in evidence}.issuperset(blueprint.tasks[0].evidence_refs)
    assert blueprint.tool_bindings[0].requirement == "lookup-evidence"


def test_provider_cannot_invent_normalized_unit(
    service: ExpertComposeService, source_file: Path
) -> None:
    service.ingest("literature-review", source_file, authorization="Repository test source")
    with pytest.raises(SynthesisError, match="unknown normalized unit"):
        service.compose("literature-review", provider=InventingProvider(), created_by="pytest")
