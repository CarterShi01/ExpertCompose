"""Small versioned HTTP boundary for deployed ExpertCompose consumers."""

from __future__ import annotations

import hmac
import json
import logging
import sqlite3
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, unquote, urlsplit

from pydantic import ValidationError

from .errors import ExpertComposeError, ProjectNotFoundError
from .service import ExpertComposeService

_LOG = logging.getLogger(__name__)
_MAX_BODY = 1_048_576


class ExpertComposeApiServer(ThreadingHTTPServer):
    """Threaded JSON server; durable state stays in the shared Workspace."""

    daemon_threads = True


def create_api_server(
    workspace: Path | str,
    *,
    host: str = "127.0.0.1",
    port: int = 8090,
    token: str = "",
    max_body_bytes: int = _MAX_BODY,
) -> ExpertComposeApiServer:
    if not token and host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("a bearer token is required when the API listens beyond loopback")
    if max_body_bytes < 1 or max_body_bytes > 16 * 1024 * 1024:
        raise ValueError("max_body_bytes must be between 1 byte and 16 MiB")
    service = ExpertComposeService(workspace)
    service.initialize()
    handler = _handler(service, token=token, max_body_bytes=max_body_bytes)
    return ExpertComposeApiServer((host, port), handler)


def serve_api(
    workspace: Path | str,
    *,
    host: str,
    port: int,
    token: str,
    max_body_bytes: int = _MAX_BODY,
) -> None:
    server = create_api_server(
        workspace,
        host=host,
        port=port,
        token=token,
        max_body_bytes=max_body_bytes,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return
    finally:
        server.server_close()


def _handler(
    service: ExpertComposeService,
    *,
    token: str,
    max_body_bytes: int,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ExpertCompose/1"
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            self._run("GET")

        def do_POST(self) -> None:
            self._run("POST")

        def do_PATCH(self) -> None:
            self._run("PATCH")

        def log_message(self, format: str, *args: Any) -> None:
            _LOG.info("api %s", format % args)

        def _run(self, method: str) -> None:
            request_id = self.headers.get("X-Request-ID", "").strip() or uuid.uuid4().hex
            if len(request_id) > 200:
                request_id = uuid.uuid4().hex
            try:
                target = urlsplit(self.path)
                if target.path == "/healthz" and method == "GET":
                    self._json(HTTPStatus.OK, {"status": "ok"}, request_id)
                    return
                if target.path == "/readyz" and method == "GET":
                    service.workspace.initialize()
                    self._json(HTTPStatus.OK, {"status": "ready"}, request_id)
                    return
                actor = self._authenticate(token)
                payload = self._route(
                    method,
                    target.path,
                    parse_qs(target.query, keep_blank_values=True),
                    actor,
                )
                self._json(HTTPStatus.OK, payload, request_id)
            except _AuthenticationError as error:
                self._error(HTTPStatus.UNAUTHORIZED, "unauthorized", str(error), request_id)
            except PermissionError as error:
                self._error(HTTPStatus.FORBIDDEN, "forbidden", str(error), request_id)
            except (FileNotFoundError, ProjectNotFoundError, _NotFoundError) as error:
                self._error(HTTPStatus.NOT_FOUND, "not_found", str(error), request_id)
            except _ConflictError as error:
                self._error(HTTPStatus.CONFLICT, "conflict", str(error), request_id)
            except (ValidationError, ValueError, json.JSONDecodeError) as error:
                message = str(error)
                if "revision conflict" in message or "already exists" in message:
                    self._error(HTTPStatus.CONFLICT, "conflict", message, request_id)
                else:
                    self._error(HTTPStatus.BAD_REQUEST, "invalid_request", message, request_id)
            except (ExpertComposeError, sqlite3.IntegrityError) as error:
                self._error(HTTPStatus.CONFLICT, "operation_rejected", str(error), request_id)
            except Exception:
                _LOG.exception("ExpertCompose API request %s failed", request_id)
                self._error(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "internal_error",
                    "request failed",
                    request_id,
                )

        def _authenticate(self, expected: str) -> str:
            if expected:
                authorization = self.headers.get("Authorization", "")
                scheme, separator, credential = authorization.partition(" ")
                if (
                    not separator
                    or scheme.lower() != "bearer"
                    or not hmac.compare_digest(credential, expected)
                ):
                    raise _AuthenticationError("valid bearer credential required")
            actor = self.headers.get("X-ExpertCompose-Actor", "api-client").strip()
            if not actor or len(actor) > 200:
                raise ValueError("X-ExpertCompose-Actor must contain 1..200 characters")
            return actor

        def _route(
            self,
            method: str,
            path: str,
            query: dict[str, list[str]],
            actor: str,
        ) -> Any:
            parts = tuple(unquote(part) for part in path.strip("/").split("/") if part)
            if any("/" in part or "\\" in part or part in {".", ".."} for part in parts):
                raise ValueError("invalid path segment")
            if parts == ("v1", "projects"):
                if method == "GET":
                    return {"projects": service.list_projects()}
                if method == "POST":
                    body = self._body()
                    return service.create_project(
                        _required_text(body, "project_id"),
                        _required_text(body, "title"),
                        _required_text(body, "objective"),
                    )
            if len(parts) == 3 and parts[:2] == ("v1", "projects") and method == "GET":
                return service.project_status(parts[2])
            if (
                len(parts) == 4
                and parts[:2] == ("v1", "projects")
                and method == "POST"
            ):
                project_id, action = parts[2], parts[3]
                body = self._body()
                blueprint_id = _optional_text(body, "blueprint_id")
                if action == "revisions":
                    change = body.get("change")
                    if not isinstance(change, dict):
                        raise ValueError("change must be a JSON object")
                    blueprint = service.revise(
                        project_id,
                        base_release_id=_required_text(body, "base_release_id"),
                        change=cast(dict[str, Any], change),
                        authorization=_required_text(body, "authorization"),
                        created_by=actor,
                    )
                    return blueprint.model_dump(mode="json")
                if action == "source-packs":
                    pack = body.get("pack")
                    if not isinstance(pack, dict):
                        raise ValueError("pack must be a JSON object")
                    blueprint = service.import_source_pack_value(
                        project_id,
                        cast(dict[str, Any], pack),
                        authorization=_required_text(body, "authorization"),
                        license=_optional_text(body, "license") or "unknown",
                        created_by=actor,
                    )
                    return blueprint.model_dump(mode="json")
                if action == "supersede":
                    return service.supersede(
                        project_id, _required_text(body, "blueprint_id")
                    ).model_dump(mode="json")
                if action == "build":
                    build = service.build(project_id, blueprint_id)
                    return {
                        "project_id": build.project_id,
                        "blueprint_id": build.blueprint_id,
                        "package": build.package,
                        "artifact_sha256": build.artifact_sha256,
                        "unbound_required_tools": list(build.unbound_required_tools),
                    }
                if action == "evaluate":
                    return service.evaluate(project_id, blueprint_id).model_dump(mode="json")
                if action == "approve":
                    blueprint, approval = service.approve(
                        project_id,
                        blueprint_id,
                        approved_by=actor,
                        note=_optional_text(body, "note"),
                    )
                    return {
                        "blueprint": blueprint.model_dump(mode="json"),
                        "approval": approval.model_dump(mode="json"),
                    }
                if action == "publish":
                    release = service.publish(
                        project_id, blueprint_id, published_by=actor
                    )
                    return release.model_dump(mode="json", exclude={"artifact_path"})
            if parts == ("v1", "releases") and method == "GET":
                project_id = _one(query, "project_id")
                return {
                    "releases": [
                        release.model_dump(mode="json", exclude={"artifact_path"})
                        for release in service.workspace.list_releases(project_id)
                    ]
                }
            if parts == ("v1", "catalog") and method == "GET":
                scope_ref = _one(query, "scope_ref")
                if not scope_ref:
                    raise ValueError("query parameter 'scope_ref' is required")
                return service.scope_catalog(scope_ref)
            if (
                len(parts) == 4
                and parts[:2] == ("v1", "releases")
                and parts[3] == "catalog"
                and method == "GET"
            ):
                scope_refs = tuple(query.get("scope_ref", ()))
                if not scope_refs:
                    raise ValueError("at least one scope_ref is required")
                return service.release_catalog(
                    parts[2], scope_refs=scope_refs
                )
            if parts == ("v1", "scope-bindings"):
                if method == "GET":
                    rows = service.list_scope_bindings(
                        scope_ref=_one(query, "scope_ref"),
                        include_disabled=_boolean(query, "include_disabled"),
                    )
                    return {"bindings": [row.model_dump(mode="json") for row in rows]}
                if method == "POST":
                    body = self._body()
                    selector_value = body.get("role_selectors", [])
                    if not isinstance(selector_value, list):
                        raise ValueError("role_selectors must be a string list")
                    selectors: list[str] = []
                    for item in selector_value:
                        if not isinstance(item, str):
                            raise ValueError("role_selectors must be a string list")
                        selectors.append(item)
                    binding = service.create_scope_binding(
                        scope_ref=_required_text(body, "scope_ref"),
                        release_id=_required_text(body, "release_id"),
                        role_selectors=tuple(selectors),
                        created_by=actor,
                    )
                    return binding.model_dump(mode="json")
            if (
                len(parts) == 3
                and parts[:2] == ("v1", "scope-bindings")
                and method == "PATCH"
            ):
                body = self._body()
                enabled = body.get("enabled")
                revision = body.get("expected_revision")
                if type(enabled) is not bool or type(revision) is not int:
                    raise ValueError("enabled and integer expected_revision are required")
                return service.set_scope_binding_enabled(
                    parts[2], enabled=enabled, expected_revision=revision
                ).model_dump(mode="json")
            raise _NotFoundError(f"no {method} route for {path}")

        def _body(self) -> dict[str, Any]:
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
            if content_type != "application/json":
                raise ValueError("Content-Type application/json is required")
            raw_length = self.headers.get("Content-Length", "")
            try:
                length = int(raw_length)
            except ValueError as error:
                raise ValueError("a valid Content-Length is required") from error
            if length < 1 or length > max_body_bytes:
                raise ValueError(f"request body must contain 1..{max_body_bytes} bytes")
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError("request JSON body must be an object")
            return cast(dict[str, Any], value)

        def _json(self, status: HTTPStatus, value: Any, request_id: str) -> None:
            raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Request-ID", request_id)
            self.end_headers()
            self.wfile.write(raw)

        def _error(
            self,
            status: HTTPStatus,
            code: str,
            message: str,
            request_id: str,
        ) -> None:
            self._json(
                status,
                {"error": {"code": code, "message": message}, "request_id": request_id},
                request_id,
            )

    return Handler


class _AuthenticationError(Exception):
    pass


class _NotFoundError(Exception):
    pass


class _ConflictError(Exception):
    pass


def _required_text(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return item


def _optional_text(value: dict[str, Any], key: str) -> str:
    item = value.get(key, "")
    if not isinstance(item, str):
        raise ValueError(f"{key} must be a string")
    return item.strip()


def _one(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key, [])
    if len(values) > 1:
        raise ValueError(f"query parameter {key!r} may appear only once")
    return values[0] if values else ""


def _boolean(query: dict[str, list[str]], key: str) -> bool:
    value = _one(query, key)
    if not value:
        return False
    if value not in {"true", "false"}:
        raise ValueError(f"query parameter {key!r} must be true or false")
    return value == "true"


__all__ = ["ExpertComposeApiServer", "create_api_server", "serve_api"]
