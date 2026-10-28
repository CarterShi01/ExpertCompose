"""Durable local workspace with JSON artifacts and a SQLite catalog."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from collections.abc import Generator, Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .errors import ProjectNotFoundError
from .models import (
    Approval,
    EvaluationReport,
    ExpertBlueprint,
    NormalizedUnit,
    ReleaseManifest,
    SourceRecord,
    require_name,
    utc_now,
)

T = TypeVar("T", bound=BaseModel)


class Workspace:
    """Filesystem artifact store indexed by a small transactional catalog.

    JSON files are the reviewable source of truth. SQLite provides efficient
    listing and transactional uniqueness; no generated artifact is hidden in a
    database blob without a corresponding file.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.projects_dir = self.root / "projects"
        self.catalog_path = self.root / "catalog.db"

    def initialize(self) -> None:
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    sha256 TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    record_path TEXT NOT NULL,
                    UNIQUE(project_id, sha256)
                );
                CREATE TABLE IF NOT EXISTS blueprints (
                    blueprint_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    record_path TEXT NOT NULL,
                    UNIQUE(project_id, version)
                );
                CREATE TABLE IF NOT EXISTS evaluations (
                    report_id TEXT PRIMARY KEY,
                    blueprint_id TEXT NOT NULL REFERENCES blueprints(blueprint_id),
                    status TEXT NOT NULL,
                    record_path TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    blueprint_id TEXT PRIMARY KEY REFERENCES blueprints(blueprint_id),
                    record_path TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS releases (
                    release_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    record_path TEXT NOT NULL,
                    UNIQUE(project_id, version)
                );
                """
            )

    def create_project(self, project_id: str, title: str, objective: str) -> dict[str, str]:
        self.initialize()
        project_id = require_name(project_id)
        if not title.strip() or not objective.strip():
            raise ValueError("project title and objective must not be empty")
        created_at = utc_now().isoformat()
        project = {
            "schema_version": 1,
            "project_id": project_id,
            "title": title.strip(),
            "objective": objective.strip(),
            "created_at": created_at,
        }
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO projects(project_id,title,objective,created_at) VALUES(?,?,?,?)",
                (project_id, title.strip(), objective.strip(), created_at),
            )
        path = self.project_dir(project_id)
        for child in (
            "sources/raw",
            "sources/records",
            "sources/normalized",
            "evidence",
            "blueprints",
            "evaluations",
            "approvals",
            "builds",
            "releases",
        ):
            (path / child).mkdir(parents=True, exist_ok=True)
        self._write_json(path / "project.json", project)
        return {key: str(value) for key, value in project.items()}

    def list_projects(self) -> list[dict[str, str]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT project_id,title,objective,created_at FROM projects ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def project(self, project_id: str) -> dict[str, Any]:
        project_id = require_name(project_id)
        path = self.project_dir(project_id) / "project.json"
        if not path.is_file():
            raise ProjectNotFoundError(f"ExpertCompose project {project_id!r} does not exist")
        return self._read_json(path)

    def project_dir(self, project_id: str) -> Path:
        return self.projects_dir / require_name(project_id)

    def next_blueprint_version(self, project_id: str) -> int:
        self.project(project_id)
        with self._connect() as connection:
            value = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM blueprints WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
        return int(value)

    def save_source(
        self,
        record: SourceRecord,
        raw: bytes,
        units: Iterable[NormalizedUnit],
    ) -> tuple[SourceRecord, bool]:
        self.project(record.project_id)
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT record_path FROM sources WHERE project_id=? AND sha256=?",
                (record.project_id, record.sha256),
            ).fetchone()
            if existing:
                return self._load(Path(existing[0]), SourceRecord), False

            base = self.project_dir(record.project_id) / "sources"
            suffix = _safe_suffix(record.origin)
            raw_path = base / "raw" / f"{record.source_id}{suffix}"
            record_path = base / "records" / f"{record.source_id}.json"
            units_path = base / "normalized" / f"{record.source_id}.jsonl"
            self._write_bytes(raw_path, raw)
            self._write_model(record_path, record)
            self._write_jsonl(units_path, (unit.model_dump(mode="json") for unit in units))
            connection.execute(
                "INSERT INTO sources(source_id,project_id,sha256,kind,record_path) "
                "VALUES(?,?,?,?,?)",
                (
                    record.source_id,
                    record.project_id,
                    record.sha256,
                    record.kind.value,
                    str(record_path),
                ),
            )
        return record, True

    def list_sources(self, project_id: str) -> list[SourceRecord]:
        self.project(project_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record_path FROM sources WHERE project_id=? ORDER BY rowid",
                (project_id,),
            ).fetchall()
        return [self._load(Path(row[0]), SourceRecord) for row in rows]

    def source_units(self, project_id: str, source_id: str) -> list[NormalizedUnit]:
        path = self.project_dir(project_id) / "sources" / "normalized" / f"{source_id}.jsonl"
        if not path.is_file():
            raise FileNotFoundError(f"normalized source {source_id!r} does not exist")
        return [NormalizedUnit.model_validate(row) for row in self._read_jsonl(path)]

    def save_evidence(self, project_id: str, evidence: Iterable[BaseModel]) -> Path:
        self.project(project_id)
        path = self.project_dir(project_id) / "evidence" / "evidence.jsonl"
        self._write_jsonl(path, (item.model_dump(mode="json") for item in evidence))
        return path

    def load_evidence(self, project_id: str) -> list[dict[str, Any]]:
        path = self.project_dir(project_id) / "evidence" / "evidence.jsonl"
        return list(self._read_jsonl(path)) if path.is_file() else []

    def save_blueprint(self, blueprint: ExpertBlueprint) -> Path:
        self.project(blueprint.project_id)
        path = (
            self.project_dir(blueprint.project_id)
            / "blueprints"
            / (f"v{blueprint.version:04d}-{blueprint.blueprint_id}.json")
        )
        self._write_model(path, blueprint)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO blueprints(blueprint_id,project_id,version,status,sha256,record_path) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(blueprint_id) DO UPDATE SET "
                "status=excluded.status,sha256=excluded.sha256,record_path=excluded.record_path",
                (
                    blueprint.blueprint_id,
                    blueprint.project_id,
                    blueprint.version,
                    blueprint.status.value,
                    blueprint.canonical_sha256(),
                    str(path),
                ),
            )
        return path

    def blueprint(self, project_id: str, blueprint_id: str = "") -> ExpertBlueprint:
        self.project(project_id)
        query = "SELECT record_path FROM blueprints WHERE project_id=?"
        values: tuple[object, ...] = (project_id,)
        if blueprint_id:
            query += " AND blueprint_id=?"
            values = (project_id, blueprint_id)
        query += " ORDER BY version DESC LIMIT 1"
        with self._connect() as connection:
            row = connection.execute(query, values).fetchone()
        if row is None:
            raise FileNotFoundError(f"project {project_id!r} has no matching blueprint")
        return self._load(Path(row[0]), ExpertBlueprint)

    def list_blueprints(self, project_id: str) -> list[ExpertBlueprint]:
        self.project(project_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record_path FROM blueprints WHERE project_id=? ORDER BY version",
                (project_id,),
            ).fetchall()
        return [self._load(Path(row[0]), ExpertBlueprint) for row in rows]

    def save_evaluation(self, project_id: str, report: EvaluationReport) -> Path:
        path = self.project_dir(project_id) / "evaluations" / f"{report.report_id}.json"
        self._write_model(path, report)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO evaluations(report_id,blueprint_id,status,record_path) "
                "VALUES(?,?,?,?) "
                "ON CONFLICT(report_id) DO UPDATE SET "
                "status=excluded.status,record_path=excluded.record_path",
                (report.report_id, report.blueprint_id, report.status, str(path)),
            )
        return path

    def evaluation(self, blueprint_id: str, report_id: str = "") -> EvaluationReport:
        query = "SELECT record_path FROM evaluations WHERE blueprint_id=?"
        values: tuple[object, ...] = (blueprint_id,)
        if report_id:
            query += " AND report_id=?"
            values = (blueprint_id, report_id)
        query += " ORDER BY rowid DESC LIMIT 1"
        with self._connect() as connection:
            row = connection.execute(query, values).fetchone()
        if row is None:
            raise FileNotFoundError(f"blueprint {blueprint_id!r} has no matching evaluation")
        return self._load(Path(row[0]), EvaluationReport)

    def save_approval(self, project_id: str, approval: Approval) -> Path:
        path = self.project_dir(project_id) / "approvals" / f"{approval.blueprint_id}.json"
        self._write_model(path, approval)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO approvals(blueprint_id,record_path) VALUES(?,?)",
                (approval.blueprint_id, str(path)),
            )
        return path

    def approval(self, blueprint_id: str) -> Approval:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_path FROM approvals WHERE blueprint_id=?", (blueprint_id,)
            ).fetchone()
        if row is None:
            raise FileNotFoundError(f"blueprint {blueprint_id!r} has no approval")
        return self._load(Path(row[0]), Approval)

    def save_release(self, manifest: ReleaseManifest) -> Path:
        path = (
            self.project_dir(manifest.project_id)
            / "releases"
            / (f"v{manifest.version:04d}-{manifest.release_id}.json")
        )
        self._write_model(path, manifest)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO releases(release_id,project_id,version,status,record_path) "
                "VALUES(?,?,?,?,?)",
                (
                    manifest.release_id,
                    manifest.project_id,
                    manifest.version,
                    manifest.status.value,
                    str(path),
                ),
            )
        return path

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.catalog_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object in {path}")
        return value

    @staticmethod
    def _read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"expected JSON object at {path}:{number}")
            yield value

    @classmethod
    def _load(cls, path: Path, model: type[T]) -> T:
        return model.model_validate(cls._read_json(path))

    @classmethod
    def _write_model(cls, path: Path, value: BaseModel) -> None:
        cls._write_json(path, value.model_dump(mode="json"))

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        Workspace._write_bytes(path, data.encode())

    @staticmethod
    def _write_jsonl(path: Path, values: Iterable[object]) -> None:
        data = "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for value in values
        )
        Workspace._write_bytes(path, data.encode())

    @staticmethod
    def _write_bytes(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def _safe_suffix(origin: str) -> str:
    suffix = Path(origin).suffix.lower()
    return suffix if suffix in {".txt", ".md", ".pdf", ".json", ".jsonl"} else ".bin"


def parse_datetime(value: str) -> datetime:
    """Compatibility helper for adapters that receive ISO timestamps."""

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


__all__ = ["Workspace", "parse_datetime"]
