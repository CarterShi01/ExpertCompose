from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from expertcompose.models import ScopeBinding, utc_now
from expertcompose.runtime import build_release_server, release_surface_selection
from expertcompose.service import ExpertComposeService
from expertcompose.synthesis import HeuristicProvider


def _published_release(service: ExpertComposeService, source_file: Path) -> tuple[str, str]:
    service.ingest("literature-review", source_file, authorization="Repository test source")
    blueprint = service.compose(
        "literature-review", provider=HeuristicProvider(), created_by="pytest"
    )
    service.build("literature-review", blueprint.blueprint_id)
    report = service.evaluate("literature-review", blueprint.blueprint_id)
    assert report.status == "passed"
    service.approve(
        "literature-review", blueprint.blueprint_id, approved_by="domain-reviewer"
    )
    release = service.publish(
        "literature-review", blueprint.blueprint_id, published_by="release-manager"
    )
    return release.release_id, blueprint.roots[0].name


def test_scope_ref_is_an_opaque_uri() -> None:
    now = utc_now()
    with pytest.raises(ValidationError, match="scope_ref"):
        ScopeBinding(
            binding_id="bind_" + "a" * 24,
            scope_ref="apollo",
            release_id="rel_" + "b" * 24,
            created_at=now,
            updated_at=now,
            created_by="pytest",
        )


def test_binding_is_pinned_validated_idempotent_and_disableable(
    service: ExpertComposeService,
    source_file: Path,
) -> None:
    release_id, root_name = _published_release(service, source_file)
    binding = service.create_scope_binding(
        scope_ref="project://apollo",
        release_id=release_id,
        role_selectors=(root_name,),
        created_by="pytest",
    )
    assert binding.release_id == release_id
    assert binding.role_selectors == (root_name,)
    assert service.create_scope_binding(
        scope_ref="project://apollo",
        release_id=release_id,
        role_selectors=(root_name,),
        created_by="another-caller",
    ) == binding
    assert service.list_scope_bindings(scope_ref="project://apollo") == [binding]

    disabled = service.set_scope_binding_enabled(
        binding.binding_id, enabled=False, expected_revision=1
    )
    assert disabled.enabled is False
    assert disabled.revision == 2
    assert service.list_scope_bindings(scope_ref="project://apollo") == []
    assert service.list_scope_bindings(
        scope_ref="project://apollo", include_disabled=True
    ) == [disabled]
    with pytest.raises(ValueError, match="revision conflict"):
        service.set_scope_binding_enabled(
            binding.binding_id, enabled=True, expected_revision=1
        )


def test_runtime_surface_is_derived_from_enabled_scope_bindings(
    service: ExpertComposeService,
    source_file: Path,
) -> None:
    release_id, root_name = _published_release(service, source_file)
    service.create_scope_binding(
        scope_ref="project://apollo",
        release_id=release_id,
        role_selectors=(root_name,),
        created_by="pytest",
    )
    selection = release_surface_selection(
        service.workspace, release_id, ("project://apollo",)
    )
    assert selection.names == frozenset({root_name})
    server = build_release_server(
        service.workspace, release_id, scope_refs=("project://apollo",)
    )
    assert server.name == "literature-review"
    with pytest.raises(PermissionError, match="no enabled ScopeBinding"):
        release_surface_selection(
            service.workspace, release_id, ("project://missing",)
        )


def test_binding_rejects_a_selector_outside_the_release(
    service: ExpertComposeService,
    source_file: Path,
) -> None:
    release_id, _root_name = _published_release(service, source_file)
    with pytest.raises(ValueError, match="Unknown or empty Contexture selector"):
        service.create_scope_binding(
            scope_ref="project://apollo",
            release_id=release_id,
            role_selectors=("missing-role",),
            created_by="pytest",
        )
