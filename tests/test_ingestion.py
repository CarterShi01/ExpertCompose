from __future__ import annotations

import json
from pathlib import Path

import pytest

from expertcompose.errors import SourceImportError
from expertcompose.ingestion import Ingestor, detect_kind, normalize, redact
from expertcompose.models import SourceKind
from expertcompose.service import ExpertComposeService


def test_redaction_removes_common_secrets() -> None:
    value = (
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz012345\n"
        "api_key=supersecretvalue123\n"
        "github_pat_abcdefghijklmnopqrstuvwxyz"
    )
    cleaned, count = redact(value)
    assert count == 3
    assert "supersecretvalue123" not in cleaned
    assert "abcdefghijklmnopqrstuvwxyz" not in cleaned
    assert cleaned.count("REDACTED") == 3


def test_session_normalization_preserves_roles_and_locations() -> None:
    raw = json.dumps(
        {
            "conversation": [
                {"role": "user", "content": "Find the failure."},
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "The evidence conflicts."}],
                },
            ]
        }
    ).encode()
    units, media_type = normalize(raw, SourceKind.SESSION, "session.json")
    assert media_type == "application/json"
    assert [item.locator.start for item in units] == [1, 2]
    assert units[0].text.startswith("[user]")
    assert "evidence conflicts" in units[1].text


def test_ingest_is_content_addressed_and_deduplicated(
    service: ExpertComposeService, source_file: Path
) -> None:
    first, created = service.ingest(
        "literature-review",
        source_file,
        authorization="Repository test source",
    )
    second, created_again = service.ingest(
        "literature-review",
        source_file,
        authorization="A later duplicate statement",
    )
    assert created is True
    assert created_again is False
    assert first == second
    assert len(service.workspace.source_units("literature-review", first.source_id)) == 1


def test_unsupported_and_empty_sources_are_rejected(tmp_path: Path) -> None:
    assert detect_kind(Path("paper.pdf")) is SourceKind.PDF
    with pytest.raises(SourceImportError, match="unsupported source extension"):
        detect_kind(Path("archive.zip"))
    empty = tmp_path / "empty.md"
    empty.write_text("\n\n", encoding="utf-8")
    service = ExpertComposeService(tmp_path / "workspace")
    service.create_project("test", "Test", "Test empty source handling")
    with pytest.raises(SourceImportError, match="no usable text"):
        Ingestor(service.workspace).import_path("test", empty, authorization="Owned test file")
