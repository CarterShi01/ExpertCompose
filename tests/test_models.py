from __future__ import annotations

from datetime import UTC, datetime, timedelta

from expertcompose.models import ToolBinding, require_name


def test_name_normalization() -> None:
    assert require_name("Research_Review") == "research-review"


def test_binding_review_timestamp_is_workflow_metadata() -> None:
    base = ToolBinding(
        requirement="lookup-evidence",
        binding_kind="builtin",
        target="expertcompose.generated:EvidenceLookup",
        schema_sha256="a" * 64,
        reviewed_by="framework",
        reviewed_at=datetime.now(UTC),
    )
    later = base.model_copy(update={"reviewed_at": base.reviewed_at + timedelta(days=1)})
    assert base.model_dump(exclude={"reviewed_at"}) == later.model_dump(exclude={"reviewed_at"})
