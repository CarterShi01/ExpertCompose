"""Safe, bounded ingestion for documents, papers, and agent sessions."""

from __future__ import annotations

import hashlib
import io
import json
import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Literal

from pypdf import PdfReader

from .errors import SourceImportError
from .models import (
    NormalizedUnit,
    SourceKind,
    SourceLocator,
    SourceRecord,
    stable_id,
    utc_now,
)
from .workspace import Workspace

MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_UNIT_CHARS = 6000

_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_A-Za-z0-9]{16,}\b"),
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|secret|password)\b\s*[:=]\s*"
        r"([\"']?)[^\s,;\"']{8,}\2"
    ),
)


class Ingestor:
    """Normalize explicit local inputs without executing or trusting their text."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def import_path(
        self,
        project_id: str,
        path: Path | str,
        *,
        authorization: str,
        title: str = "",
        license: str = "unknown",
        kind: SourceKind | None = None,
    ) -> tuple[SourceRecord, bool]:
        source_path = Path(path).expanduser().resolve()
        if not source_path.is_file():
            raise SourceImportError(f"source path is not a readable file: {source_path}")
        size = source_path.stat().st_size
        if size > MAX_SOURCE_BYTES:
            raise SourceImportError(
                f"source is {size} bytes; MVP limit is {MAX_SOURCE_BYTES} bytes per file"
            )
        raw = source_path.read_bytes()
        detected = kind or detect_kind(source_path)
        units, media_type = normalize(raw, detected, source_path.name)
        if not units:
            raise SourceImportError(f"source {source_path} contains no usable text")
        digest = hashlib.sha256(raw).hexdigest()
        source_id = stable_id("src", project_id, digest)
        bound_units = tuple(unit.model_copy(update={"source_id": source_id}) for unit in units)
        record = SourceRecord(
            source_id=source_id,
            project_id=project_id,
            kind=detected,
            title=(title.strip() or source_path.stem)[:300],
            origin=str(source_path),
            sha256=digest,
            media_type=media_type,
            byte_count=len(raw),
            imported_at=utc_now(),
            authorization=authorization,
            license=license,
            metadata={
                "unit_count": len(bound_units),
                "redaction_count": sum(item.redactions for item in bound_units),
                "normalization": "expertcompose-v1",
            },
        )
        return self.workspace.save_source(record, raw, bound_units)

    def import_many(
        self,
        project_id: str,
        paths: Iterable[Path | str],
        *,
        authorization: str,
        license: str = "unknown",
    ) -> list[tuple[SourceRecord, bool]]:
        return [
            self.import_path(project_id, path, authorization=authorization, license=license)
            for path in paths
        ]


def detect_kind(path: Path) -> SourceKind:
    suffix = path.suffix.lower()
    mapping = {
        ".txt": SourceKind.TEXT,
        ".md": SourceKind.MARKDOWN,
        ".markdown": SourceKind.MARKDOWN,
        ".pdf": SourceKind.PDF,
        ".json": SourceKind.JSON,
        ".jsonl": SourceKind.JSONL,
        ".ndjson": SourceKind.JSONL,
    }
    if suffix not in mapping:
        raise SourceImportError(
            f"unsupported source extension {suffix!r}; use txt, md, pdf, json, or jsonl"
        )
    return mapping[suffix]


def normalize(raw: bytes, kind: SourceKind, label: str) -> tuple[tuple[NormalizedUnit, ...], str]:
    if kind in {SourceKind.TEXT, SourceKind.MARKDOWN}:
        text = _decode(raw, label)
        media_type = "text/markdown" if kind is SourceKind.MARKDOWN else "text/plain"
        return tuple(_text_units(text)), media_type
    if kind in {SourceKind.PDF, SourceKind.PAPER}:
        return tuple(_pdf_units(raw)), "application/pdf"
    if kind in {SourceKind.SESSION, SourceKind.JSON, SourceKind.JSONL}:
        return tuple(_session_units(raw, kind, label)), (
            "application/x-ndjson" if kind is SourceKind.JSONL else "application/json"
        )
    raise SourceImportError(f"source kind {kind!r} is not supported")


def redact(text: str) -> tuple[str, int]:
    """Remove common credentials before source material enters a model prompt."""

    result, count = text, 0
    for pattern in _SECRET_PATTERNS:
        result, found = pattern.subn(_redaction_replacement, result)
        count += found
    return result, count


def _redaction_replacement(match: re.Match[str]) -> str:
    if match.lastindex and match.lastindex >= 1 and match.group(1).lower().startswith("bearer"):
        return match.group(1) + "[REDACTED]"
    if (
        match.lastindex
        and match.lastindex >= 1
        and match.group(1).lower()
        in {
            "api_key",
            "api-key",
            "apikey",
            "access_token",
            "access-token",
            "accesstoken",
            "secret",
            "password",
        }
    ):
        return match.group(1) + "=[REDACTED]"
    return "[REDACTED_SECRET]"


def _decode(raw: bytes, label: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SourceImportError(f"{label} is not valid UTF-8 text") from error


def _text_units(text: str) -> Iterator[NormalizedUnit]:
    lines = text.splitlines()
    start, buffer = 1, []
    size = 0
    for number, line in enumerate(lines, 1):
        addition = len(line) + 1
        if buffer and size + addition > MAX_UNIT_CHARS:
            yield _unit("line", start, number - 1, "\n".join(buffer))
            start, buffer, size = number, [], 0
        buffer.append(line)
        size += addition
        if not line.strip() and size >= MAX_UNIT_CHARS // 2:
            yield _unit("line", start, number, "\n".join(buffer))
            start, buffer, size = number + 1, [], 0
    if buffer and any(line.strip() for line in buffer):
        yield _unit("line", start, max(start, len(lines)), "\n".join(buffer))


def _pdf_units(raw: bytes) -> Iterator[NormalizedUnit]:
    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as error:
        raise SourceImportError(f"PDF could not be parsed: {error}") from error
    if len(reader.pages) > 5000:
        raise SourceImportError("PDF exceeds the 5000-page MVP safety limit")
    for page_number, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception as error:
            raise SourceImportError(f"failed to extract PDF page {page_number}: {error}") from error
        for index, part in enumerate(_chunks(text, MAX_UNIT_CHARS), 1):
            label = f"page {page_number}" + (
                f", part {index}" if len(text) > MAX_UNIT_CHARS else ""
            )
            yield _unit("page", page_number, page_number, part, label)


def _session_units(raw: bytes, kind: SourceKind, label: str) -> Iterator[NormalizedUnit]:
    text = _decode(raw, label)
    payloads: list[Any]
    if kind is SourceKind.JSONL:
        payloads = []
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                payloads.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise SourceImportError(f"invalid JSONL at {label}:{number}: {error}") from error
    else:
        try:
            payloads = [json.loads(text)]
        except json.JSONDecodeError as error:
            raise SourceImportError(f"invalid JSON in {label}: {error}") from error

    message_number = 0
    for payload in payloads:
        for message in _messages(payload):
            content = _message_content(message)
            if not content.strip():
                continue
            message_number += 1
            role = str(message.get("role") or message.get("author") or "unknown")
            timestamp = str(message.get("created_at") or message.get("timestamp") or "")
            header = f"[{role}]" + (f" {timestamp}" if timestamp else "")
            for part in _chunks(content, MAX_UNIT_CHARS - len(header) - 1):
                yield _unit(
                    "message",
                    message_number,
                    message_number,
                    header + "\n" + part,
                    f"message {message_number} ({role})",
                )


def _messages(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from _messages(item)
        return
    if not isinstance(value, dict):
        return
    if "role" in value and any(key in value for key in ("content", "text", "parts")):
        yield value
        return
    for key in ("messages", "conversation", "turns", "session", "sessions", "data"):
        nested = value.get(key)
        if isinstance(nested, (dict, list)):
            yield from _messages(nested)


def _message_content(message: dict[str, Any]) -> str:
    value = message.get("content", message.get("text", message.get("parts", "")))
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                content = item.get("text") or item.get("content")
                if isinstance(content, str):
                    parts.append(content)
        return "\n".join(parts)
    return str(value) if value is not None else ""


def _unit(
    unit: Literal["line", "page", "message", "chunk"],
    start: int,
    end: int,
    text: str,
    label: str = "",
) -> NormalizedUnit:
    sanitized, redactions = redact(text.strip())
    digest = hashlib.sha256(sanitized.encode()).hexdigest()
    return NormalizedUnit(
        source_id="src_" + "0" * 24,
        locator=SourceLocator(unit=unit, start=start, end=end, label=label),
        text=sanitized,
        sha256=digest,
        redactions=redactions,
    )


def _chunks(text: str, maximum: int) -> list[str]:
    compact = text.strip()
    if not compact:
        return []
    return [compact[index : index + maximum] for index in range(0, len(compact), maximum)]


__all__ = [
    "MAX_SOURCE_BYTES",
    "MAX_UNIT_CHARS",
    "Ingestor",
    "detect_kind",
    "normalize",
    "redact",
]
