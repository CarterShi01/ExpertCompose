"""Dependency-light command line interface for the complete MVP lifecycle."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .errors import ExpertComposeError
from .service import ExpertComposeService
from .synthesis import HeuristicProvider, OpenAICompatibleProvider


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    if not getattr(arguments, "command", None):
        parser.print_help()
        return 0
    service = ExpertComposeService(arguments.workspace)
    try:
        result = _dispatch(service, arguments)
        if result is not None:
            print(json.dumps(_jsonable(result), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (ExpertComposeError, FileNotFoundError, FileExistsError, ValueError) as error:
        print(f"expertcompose: {error}", file=sys.stderr)
        return 2


def _dispatch(service: ExpertComposeService, args: argparse.Namespace) -> Any:
    if args.command == "init":
        return {"workspace": str(service.initialize())}
    if args.command == "project":
        if args.project_command == "create":
            return service.create_project(args.project_id, args.title, args.objective)
        if args.project_command == "list":
            return {"projects": service.list_projects()}
        if args.project_command == "status":
            return service.project_status(args.project_id)
    if args.command == "ingest":
        rows = []
        for path in args.paths:
            record, created = service.ingest(
                args.project_id,
                path,
                authorization=args.authorization,
                license=args.license,
                title=args.title if len(args.paths) == 1 else "",
            )
            rows.append({"created": created, "source": record})
        return {"sources": rows}
    if args.command == "compose":
        if args.provider == "heuristic":
            provider = HeuristicProvider()
        else:
            api_key = os.environ.get(args.api_key_env, "")
            if not api_key:
                raise ValueError(f"environment variable {args.api_key_env} is required")
            provider = OpenAICompatibleProvider(
                model=args.model,
                api_key=api_key,
                base_url=args.base_url,
            )
        return service.compose(args.project_id, provider=provider, created_by=args.created_by)
    if args.command == "build":
        return service.build(args.project_id, args.blueprint_id)
    if args.command == "suite":
        suite = service.suite(args.project_id, args.blueprint_id)
        template = service.observations_template(args.project_id, args.blueprint_id)
        return {"suite": suite, "observations_template": str(template)}
    if args.command == "evaluate":
        return service.evaluate(
            args.project_id,
            args.blueprint_id,
            observations_path=args.observations,
            require_behavioral=args.require_behavioral,
        )
    if args.command == "approve":
        blueprint, approval = service.approve(
            args.project_id,
            args.blueprint_id,
            approved_by=args.approved_by,
            note=args.note,
        )
        return {"blueprint": blueprint, "approval": approval}
    if args.command == "publish":
        return service.publish(
            args.project_id,
            args.blueprint_id,
            published_by=args.published_by,
        )
    if args.command == "serve":
        from .mcp import serve

        return serve(service.workspace.root, transport=args.transport, port=args.port)
    raise ValueError("unknown command")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="expertcompose",
        description="Compile source material into governed, agent-ready ExpertNets.",
    )
    parser.add_argument(
        "--workspace",
        default=os.environ.get("EXPERTCOMPOSE_WORKSPACE", ".expertcompose"),
        help="Durable workspace root (default: .expertcompose).",
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("init", help="Initialize the durable workspace.")

    project = commands.add_parser("project", help="Create and inspect projects.")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    create = project_commands.add_parser("create")
    create.add_argument("project_id")
    create.add_argument("--title", required=True)
    create.add_argument("--objective", required=True)
    project_commands.add_parser("list")
    status = project_commands.add_parser("status")
    status.add_argument("project_id")

    ingest = commands.add_parser("ingest", help="Import explicit local source files.")
    ingest.add_argument("project_id")
    ingest.add_argument("paths", nargs="+")
    ingest.add_argument("--authorization", required=True)
    ingest.add_argument("--license", default="unknown")
    ingest.add_argument("--title", default="")

    compose = commands.add_parser("compose", help="Create a source-grounded Blueprint draft.")
    compose.add_argument("project_id")
    compose.add_argument("--provider", choices=("heuristic", "openai"), default="heuristic")
    compose.add_argument("--model", default="")
    compose.add_argument("--base-url", default="https://api.openai.com/v1")
    compose.add_argument("--api-key-env", default="EXPERTCOMPOSE_API_KEY")
    compose.add_argument("--created-by", default=os.environ.get("USER", "local-user"))

    build = commands.add_parser("build", help="Generate a standalone Contexture project.")
    _blueprint_arguments(build)
    suite = commands.add_parser("suite", help="Export held-out tasks and receipt template.")
    _blueprint_arguments(suite)
    evaluate = commands.add_parser("evaluate", help="Run release gates.")
    _blueprint_arguments(evaluate)
    evaluate.add_argument("--observations", type=Path)
    evaluate.add_argument("--require-behavioral", action="store_true")
    approve = commands.add_parser("approve", help="Approve exact passing Blueprint bytes.")
    _blueprint_arguments(approve)
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--note", default="")
    publish = commands.add_parser("publish", help="Publish an immutable local release.")
    _blueprint_arguments(publish)
    publish.add_argument("--published-by", required=True)

    serve = commands.add_parser("serve", help="Serve ExpertCompose operations over MCP.")
    serve.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    serve.add_argument("--port", type=int, default=8080)
    return parser


def _blueprint_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_id")
    parser.add_argument("--blueprint-id", default="")


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return {
            key: _jsonable(item)
            for key, item in asdict(value).items()  # pyright: ignore[reportArgumentType]
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
