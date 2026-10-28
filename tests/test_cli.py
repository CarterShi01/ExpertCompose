from __future__ import annotations

import json
from pathlib import Path

from expertcompose.cli import main


def test_cli_project_flow(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    assert main(["--workspace", str(workspace), "init"]) == 0
    assert (
        main(
            [
                "--workspace",
                str(workspace),
                "project",
                "create",
                "test-project",
                "--title",
                "Test Project",
                "--objective",
                "Test the CLI facade",
            ]
        )
        == 0
    )
    project = json.loads((workspace / "projects" / "test-project" / "project.json").read_text())
    assert project["project_id"] == "test-project"
