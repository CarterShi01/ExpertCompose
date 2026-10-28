from __future__ import annotations

from pathlib import Path

import pytest

from expertcompose.service import ExpertComposeService


@pytest.fixture
def service(tmp_path: Path) -> ExpertComposeService:
    value = ExpertComposeService(tmp_path / "workspace")
    value.initialize()
    value.create_project(
        "literature-review",
        "Literature Review",
        "Produce evidence-traceable reviews without hiding conflicting results.",
    )
    return value


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "method.md"
    path.write_text(
        """# Review method

First define the question and inclusion criteria. Then extract each material
claim and its exact source. Never hide contradictory evidence. Report unknowns
and scope limits before writing a conclusion.

The review must identify unsupported generalization and propose the minimum
additional evidence required.
""",
        encoding="utf-8",
    )
    return path
