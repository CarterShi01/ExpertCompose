from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Thread

import httpx

from expertcompose.api import create_api_server
from expertcompose.service import ExpertComposeService
from expertcompose.source_pack import source_pack_digest
from expertcompose.synthesis import HeuristicProvider


def _publish(service: ExpertComposeService, source_file: Path) -> tuple[str, str]:
    service.ingest(
        "literature-review", source_file, authorization="Repository test source"
    )
    blueprint = service.compose(
        "literature-review", provider=HeuristicProvider(), created_by="pytest"
    )
    service.build("literature-review", blueprint.blueprint_id)
    assert service.evaluate("literature-review", blueprint.blueprint_id).status == "passed"
    service.approve(
        "literature-review", blueprint.blueprint_id, approved_by="domain-reviewer"
    )
    release = service.publish(
        "literature-review", blueprint.blueprint_id, published_by="release-manager"
    )
    return release.release_id, blueprint.roots[0].name


def test_api_auth_scoped_catalog_and_binding_lifecycle(
    service: ExpertComposeService,
    source_file: Path,
) -> None:
    release_id, root_name = _publish(service, source_file)
    server = create_api_server(
        service.workspace.root, host="127.0.0.1", port=0, token="test-token"
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=base_url, timeout=5) as anonymous:
            assert anonymous.get("/healthz").json() == {"status": "ok"}
            assert anonymous.get("/v1/releases").status_code == 401

        headers = {
            "Authorization": "Bearer test-token",
            "X-ExpertCompose-Actor": "pytest",
        }
        with httpx.Client(base_url=base_url, headers=headers, timeout=5) as client:
            releases = client.get("/v1/releases")
            assert releases.status_code == 200
            release_value = releases.json()["releases"][0]
            assert release_value["release_id"] == release_id
            assert "artifact_path" not in release_value
            assert client.get(f"/v1/releases/{release_id}/catalog").status_code == 400

            created = client.post("/v1/scope-bindings", json={
                "scope_ref": "project://apollo",
                "release_id": release_id,
                "role_selectors": [root_name],
            })
            assert created.status_code == 200, created.text
            binding = created.json()
            assert binding["created_by"] == "pytest"

            catalog = client.get(
                f"/v1/releases/{release_id}/catalog",
                params={"scope_ref": "project://apollo"},
            )
            assert catalog.status_code == 200, catalog.text
            value = catalog.json()
            assert value["release"]["release_id"] == release_id
            assert "artifact_path" not in value["release"]
            assert value["role_selectors"] == [root_name]
            assert value["catalog_sha256"] == value["release"]["blueprint_sha256"]
            assert value["blueprint"]["roots"][0]["name"] == root_name

            denied = client.get(
                f"/v1/releases/{release_id}/catalog",
                params={"scope_ref": "project://missing"},
            )
            assert denied.status_code == 403

            def disable() -> httpx.Response:
                return httpx.patch(
                    base_url + f"/v1/scope-bindings/{binding['binding_id']}",
                    headers=headers,
                    json={"enabled": False, "expected_revision": 1},
                    timeout=5,
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(disable) for _index in range(2)]
                disabled = [future.result() for future in futures]
            assert sorted(response.status_code for response in disabled) == [200, 409]
            winner = next(response for response in disabled if response.status_code == 200)
            assert winner.json()["revision"] == 2
            assert client.get(
                f"/v1/releases/{release_id}/catalog",
                params={"scope_ref": "project://apollo"},
            ).status_code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_api_requires_authentication_off_loopback(service: ExpertComposeService) -> None:
    try:
        create_api_server(service.workspace.root, host="0.0.0.0", port=0)
    except ValueError as error:
        assert "bearer token" in str(error)
    else:
        raise AssertionError("an unauthenticated non-loopback API was admitted")


def test_api_runs_remote_source_pack_release_lifecycle(
    service: ExpertComposeService,
) -> None:
    role_instructions = "Review the exact evidence and report unsupported conclusions."
    skill_instructions = "Check provenance before accepting a material claim."
    pack: dict[str, object] = {
        "format": "expertcompose.source-pack.v1",
        "name": "remote-team",
        "title": "Remote Team",
        "objective": "Publish one remotely submitted reviewed expert.",
        "roles": [{
            "name": "reviewer",
            "description": "Reviews evidence-backed work.",
            "instructions": role_instructions,
            "path": ["quality"],
            "skills": ["provenance-review"],
            "tools": ["lookup-evidence"],
            "annotations": {},
        }],
        "skills": [{
            "name": "provenance-review",
            "description": "Verify provenance.",
            "instructions": skill_instructions,
        }],
        "messages": [
            {"role": "role:reviewer", "content": role_instructions},
            {"role": "skill:provenance-review", "content": skill_instructions},
        ],
    }
    pack["content_sha256"] = source_pack_digest(pack)
    server = create_api_server(
        service.workspace.root, host="127.0.0.1", port=0, token="lifecycle-token"
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    headers = {
        "Authorization": "Bearer lifecycle-token",
        "X-ExpertCompose-Actor": "release-operator",
    }
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}",
            headers=headers,
            timeout=5,
        ) as client:
            draft = client.post(
                "/v1/projects/literature-review/source-packs",
                json={"authorization": "reviewed test pack", "pack": pack},
            )
            assert draft.status_code == 200, draft.text
            blueprint_id = draft.json()["blueprint_id"]
            body = {"blueprint_id": blueprint_id}
            assert client.post(
                "/v1/projects/literature-review/build", json=body
            ).status_code == 200
            evaluation = client.post(
                "/v1/projects/literature-review/evaluate", json=body
            )
            assert evaluation.json()["status"] == "passed"
            approval = client.post(
                "/v1/projects/literature-review/approve", json=body
            )
            assert approval.json()["approval"]["approved_by"] == "release-operator"
            published = client.post(
                "/v1/projects/literature-review/publish", json=body
            )
            assert published.status_code == 200, published.text
            release = published.json()
            assert "artifact_path" not in release
            binding = client.post("/v1/scope-bindings", json={
                "scope_ref": "project://remote",
                "release_id": release["release_id"],
                "role_selectors": ["team/*"],
            })
            assert binding.status_code == 200, binding.text
            catalog = client.get(
                f"/v1/releases/{release['release_id']}/catalog",
                params={"scope_ref": "project://remote"},
            )
            assert catalog.status_code == 200, catalog.text
            team = catalog.json()["blueprint"]["roots"][0]
            assert team["children"][0]["children"][0]["name"] == "reviewer"
            resolved = client.get(
                "/v1/catalog", params={"scope_ref": "project://remote"}
            )
            assert resolved.status_code == 200, resolved.text
            assert resolved.json()["release"]["release_id"] == release["release_id"]

            revision = client.post(
                "/v1/projects/literature-review/revisions",
                json={
                    "base_release_id": release["release_id"],
                    "authorization": "reviewed remote change",
                    "change": {
                        "kind": "skill",
                        "name": "provenance-review",
                        "target_scope": "resource",
                        "title": "Improve provenance review",
                        "reason": "Target-host review passed.",
                        "effect": "Tighten the existing Skill.",
                        "source": "team-construction:remote",
                        "idempotency_key": "remote-change-1",
                        "body": "skill_md: Verify exact source locators.",
                        "body_value": {
                            "skill_md": "Verify exact source locators before accepting claims."
                        },
                    },
                },
            )
            assert revision.status_code == 200, revision.text
            revised = revision.json()
            assert revised["status"] == "draft"
            dismissed = client.post(
                "/v1/projects/literature-review/supersede",
                json={"blueprint_id": revised["blueprint_id"]},
            )
            assert dismissed.status_code == 200, dismissed.text
            assert dismissed.json()["status"] == "superseded"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
