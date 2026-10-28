"""Load approved ExpertNet artifacts and resolve their Contexture surfaces."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from contexture import Principal
from contexture.core.model import SurfaceSelection
from contexture.server import ContextureOptions, compile_application
from contexture.server.root_selector import HeaderSurfaceSelector

from .models import ReleaseManifest
from .workspace import Workspace


def canonical_release_selectors(
    release: ReleaseManifest,
    selectors: tuple[str, ...],
) -> tuple[str, ...]:
    """Validate selectors against an exact release and return resolved roots."""

    if not selectors:
        return ()
    module = _load_release(release)
    try:
        compiled = compile_application(cast(Any, module).app)
        resolved = SurfaceSelection.only(selectors).resolve(compiled.index)
        return tuple(sorted(resolved.names or ()))
    finally:
        _unload(module.__name__)


def release_surface_selection(
    workspace: Workspace,
    release_id: str,
    scope_refs: tuple[str, ...] = (),
) -> SurfaceSelection:
    """Resolve the fixed maximum surface for one release and set of Scopes."""

    release = workspace.release(release_id)
    if not scope_refs:
        return SurfaceSelection.all()
    selected: set[str] = set()
    found = False
    for scope_ref in dict.fromkeys(scope_refs):
        bindings = workspace.list_scope_bindings(scope_ref=scope_ref, enabled=True)
        for binding in bindings:
            if binding.release_id != release.release_id:
                continue
            found = True
            if not binding.role_selectors:
                return SurfaceSelection.all()
            selected.update(binding.role_selectors)
    if not found:
        raise PermissionError(
            f"no enabled ScopeBinding grants release {release_id!r} to the requested Scopes"
        )
    return SurfaceSelection.only(tuple(sorted(selected)))


def build_release_server(
    workspace: Workspace,
    release_id: str,
    *,
    scope_refs: tuple[str, ...] = (),
) -> Any:
    """Build a Runtime MCP server with a fixed ceiling and request attenuation."""

    release = workspace.release(release_id)
    ceiling = release_surface_selection(workspace, release_id, scope_refs)
    module = _load_release(release)
    try:
        compiled = compile_application(cast(Any, module).app)
        resolved_ceiling = ceiling.resolve(compiled.index)

        def fixed_ceiling(_principal: Principal | None) -> SurfaceSelection:
            return resolved_ceiling

        return compiled.server(
            surface_selector=HeaderSurfaceSelector(ceiling=fixed_ceiling)
        )
    finally:
        _unload(module.__name__)


def serve_release(
    workspace: Workspace,
    release_id: str,
    *,
    scope_refs: tuple[str, ...],
    transport: str,
    port: int,
) -> None:
    server = build_release_server(workspace, release_id, scope_refs=scope_refs)
    options = (
        ContextureOptions(transport="stdio")
        if transport == "stdio"
        else ContextureOptions(transport="streamable-http", port=port)
    )
    server.start(options)


def _load_release(release: ReleaseManifest) -> ModuleType:
    artifact = Path(release.artifact_path)
    manifest_path = artifact / "build-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"release build manifest is missing: {manifest_path}")
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    package = str(value["package"])
    package_dir = artifact / "src" / package
    entrypoint = package_dir / "__init__.py"
    if not entrypoint.is_file():
        raise FileNotFoundError(f"release package is missing: {entrypoint}")
    alias = f"_expertcompose_release_{release.release_id}"
    _unload(alias)
    spec = importlib.util.spec_from_file_location(
        alias,
        entrypoint,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load release package {entrypoint}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        _unload(alias)
        raise
    return module


def _unload(alias: str) -> None:
    for name in tuple(sys.modules):
        if name == alias or name.startswith(alias + "."):
            sys.modules.pop(name, None)


__all__ = [
    "build_release_server",
    "canonical_release_selectors",
    "release_surface_selection",
    "serve_release",
]
