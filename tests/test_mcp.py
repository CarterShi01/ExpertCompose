from __future__ import annotations

from pathlib import Path

import pytest
from contexture.server import compile_application

from expertcompose.mcp import ExpertComposeChannels, app


def test_mcp_application_compiles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXPERTCOMPOSE_WORKSPACE", str(tmp_path / "workspace"))
    compiled = compile_application(app)
    refs = {ref for ref, _node in compiled.index.walk()}
    assert "expert-compose" in refs
    assert any(ref.endswith("/publish-expert-net") for ref in refs)
    assert any(ref.endswith("/create-scope-binding") for ref in refs)


def test_mcp_import_allowlist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    source = allowed / "source.md"
    source.write_text("Authorized source", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("Outside source", encoding="utf-8")
    monkeypatch.setenv("EXPERTCOMPOSE_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("EXPERTCOMPOSE_IMPORT_ROOTS", str(allowed))
    channels = ExpertComposeChannels()
    assert channels.allowed_import(str(source)) == source.resolve()
    with pytest.raises(PermissionError, match="outside"):
        channels.allowed_import(str(outside))


def test_mcp_import_is_disabled_without_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.md"
    source.write_text("Source", encoding="utf-8")
    monkeypatch.setenv("EXPERTCOMPOSE_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.delenv("EXPERTCOMPOSE_IMPORT_ROOTS", raising=False)
    with pytest.raises(PermissionError, match="disabled"):
        ExpertComposeChannels().allowed_import(str(source))
