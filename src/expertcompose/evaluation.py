"""Deterministic gates plus neutral receipts for behavioral evaluation."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from contexture.server import compile_application

from .generator import BuildResult
from .models import (
    BlueprintStatus,
    CheckResult,
    EvaluationCase,
    EvaluationObservation,
    EvaluationReport,
    EvaluationSuite,
    ExpertBlueprint,
    RoleBlueprint,
    stable_id,
    utc_now,
)
from .workspace import Workspace


class ExpertNetEvaluator:
    """Evaluate exact Blueprint bytes and their generated Contexture artifact."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def suite(self, blueprint: ExpertBlueprint) -> EvaluationSuite:
        cases = tuple(
            EvaluationCase(
                case_id=stable_id("case", blueprint.blueprint_id, task.task_id, length=20),
                task_ref=task.task_id,
                prompt=(
                    f"Complete this task using only the published expert system: {task.description}"
                ),
                rubric=task.success_criteria,
                held_out=True,
            )
            for task in blueprint.tasks
        )
        return EvaluationSuite(
            suite_id=stable_id("suite", blueprint.blueprint_id, length=20),
            blueprint_id=blueprint.blueprint_id,
            cases=cases,
            created_at=utc_now(),
        )

    def evaluate(
        self,
        blueprint: ExpertBlueprint,
        build: BuildResult,
        *,
        observations: Iterable[EvaluationObservation] = (),
        require_behavioral: bool = False,
    ) -> EvaluationReport:
        evidence_rows = self.workspace.load_evidence(blueprint.project_id)
        evidence_ids = {str(item["evidence_id"]) for item in evidence_rows}
        source_ids = {str(item["source_id"]) for item in evidence_rows}
        checks = [
            self._grounding(blueprint, evidence_ids),
            self._source_coverage(blueprint, source_ids),
            self._shape(blueprint),
            self._bindings(blueprint),
            self._generated_contexture(build),
            self._behavioral(blueprint, tuple(observations), require_behavioral),
        ]
        status = "failed" if any(item.status == "failed" for item in checks) else "passed"
        report = EvaluationReport(
            report_id=stable_id(
                "eval",
                blueprint.blueprint_id,
                blueprint.canonical_sha256(),
                json.dumps([item.model_dump(mode="json") for item in checks], sort_keys=True),
            ),
            blueprint_id=blueprint.blueprint_id,
            blueprint_sha256=blueprint.canonical_sha256(),
            status=status,
            checks=tuple(checks),
            created_at=utc_now(),
            evaluator="expertcompose-evaluator-v1",
        )
        self.workspace.save_evaluation(blueprint.project_id, report)
        if status == "passed":
            self.workspace.save_blueprint(
                blueprint.model_copy(update={"status": BlueprintStatus.EVALUATED})
            )
        return report

    @staticmethod
    def _grounding(blueprint: ExpertBlueprint, evidence_ids: set[str]) -> CheckResult:
        refs = list(_all_evidence_refs(blueprint))
        unknown = sorted(set(refs) - evidence_ids)
        metric = (sum(ref in evidence_ids for ref in refs) / len(refs)) if refs else 0.0
        return CheckResult(
            check_id="evidence-grounding",
            status="failed" if unknown or not refs else "passed",
            summary=(
                "Every authored artifact resolves to persisted evidence."
                if not unknown and refs
                else f"Unknown or absent evidence references: {unknown or ['no references']}"
            ),
            metric=metric,
            evidence_refs=tuple(unknown[:20]),
        )

    @staticmethod
    def _source_coverage(blueprint: ExpertBlueprint, source_ids: set[str]) -> CheckResult:
        missing = sorted(set(blueprint.source_ids) - source_ids)
        ratio = (
            len(set(blueprint.source_ids) & source_ids) / len(blueprint.source_ids)
            if blueprint.source_ids
            else 0.0
        )
        return CheckResult(
            check_id="source-coverage",
            status="warning" if missing else "passed",
            summary=(
                "Every imported source contributes evidence."
                if not missing
                else "Some imported sources contribute no selected evidence: " + ", ".join(missing)
            ),
            metric=ratio,
        )

    @staticmethod
    def _shape(blueprint: ExpertBlueprint) -> CheckResult:
        roles = list(_roles(blueprint.roots))
        depth = max((len(path) for path, _ in roles), default=0)
        broad = [
            ("/".join(path), len(role.children)) for path, role in roles if len(role.children) > 12
        ]
        empty = [
            "/".join(path)
            for path, role in roles
            if not role.children and not role.skills and not role.tool_requirements
        ]
        failed = depth > 8 or bool(broad) or bool(empty)
        details = []
        if depth > 8:
            details.append(f"depth {depth} exceeds 8")
        if broad:
            details.append(f"roles exceed 12 child branches: {broad}")
        if empty:
            details.append(f"roles have no actionable members: {empty}")
        return CheckResult(
            check_id="expert-net-shape",
            status="failed" if failed else "passed",
            summary="; ".join(details)
            if details
            else f"Navigable shape: {len(roles)} Roles, depth {depth}.",
            metric=float(depth),
        )

    @staticmethod
    def _bindings(blueprint: ExpertBlueprint) -> CheckResult:
        bound = {item.requirement for item in blueprint.tool_bindings}
        missing = sorted(
            item.name
            for item in blueprint.tool_requirements
            if item.required and item.name not in bound
        )
        return CheckResult(
            check_id="required-tool-bindings",
            status="failed" if missing else "passed",
            summary=(
                "Every required Tool has a reviewed binding."
                if not missing
                else "Required Tool requirements are unbound: " + ", ".join(missing)
            ),
            metric=float(len(missing)),
        )

    @staticmethod
    def _generated_contexture(build: BuildResult) -> CheckResult:
        package_dir = build.path / "src" / build.package
        alias = "_expertcompose_eval_" + build.artifact_sha256[:16]
        spec = importlib.util.spec_from_file_location(
            alias,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
        if spec is None or spec.loader is None:
            return CheckResult(
                check_id="contexture-compilation",
                status="failed",
                summary="Generated package could not be loaded.",
            )
        try:
            module = importlib.util.module_from_spec(spec)
            sys.modules[alias] = module
            spec.loader.exec_module(module)
            application = module.app
            compiled = compile_application(application)
            refs = [ref for ref, _node in compiled.index.walk()]
            if not refs:
                raise ValueError("compiled Index contains no nodes")
            return CheckResult(
                check_id="contexture-compilation",
                status="passed",
                summary=(
                    f"Generated Contexture application compiles with {len(refs)} canonical refs."
                ),
                metric=float(len(refs)),
            )
        except Exception as error:
            return CheckResult(
                check_id="contexture-compilation",
                status="failed",
                summary=(
                    f"Generated Contexture application was refused: {type(error).__name__}: {error}"
                ),
            )
        finally:
            for name in list(sys.modules):
                if name == alias or name.startswith(alias + "."):
                    sys.modules.pop(name, None)

    def _behavioral(
        self,
        blueprint: ExpertBlueprint,
        observations: tuple[EvaluationObservation, ...],
        required: bool,
    ) -> CheckResult:
        suite = self.suite(blueprint)
        expected = {case.case_id for case in suite.cases}
        by_case = {item.case_id: item for item in observations}
        missing = expected - set(by_case)
        failures = sorted(case_id for case_id, item in by_case.items() if not item.passed)
        if not observations:
            return CheckResult(
                check_id="behavioral-receipts",
                status="failed" if required else "skipped",
                summary=(
                    "Behavioral receipts are required but none were supplied."
                    if required
                    else (
                        "No host behavioral receipts supplied; deterministic release gates "
                        "still ran."
                    )
                ),
                metric=0.0,
            )
        passed = not missing and not failures and set(by_case).issubset(expected)
        ratio = sum(item.passed for item in observations) / len(expected) if expected else 0.0
        details = []
        if missing:
            details.append("missing: " + ", ".join(sorted(missing)))
        if failures:
            details.append("failed: " + ", ".join(failures))
        unknown = set(by_case) - expected
        if unknown:
            details.append("unknown: " + ", ".join(sorted(unknown)))
        return CheckResult(
            check_id="behavioral-receipts",
            status="passed" if passed else "failed",
            summary="All held-out cases passed." if passed else "; ".join(details),
            metric=ratio,
        )


def load_observations(path: Path | str) -> tuple[EvaluationObservation, ...]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    rows: Any = value.get("observations") if isinstance(value, dict) else value
    if not isinstance(rows, list):
        raise ValueError("behavioral receipt must be a list or an observations object")
    return tuple(EvaluationObservation.model_validate(item) for item in rows)


def _roles(
    roots: tuple[RoleBlueprint, ...], prefix: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], RoleBlueprint]]:
    for role in roots:
        path = (*prefix, role.name)
        yield path, role
        yield from _roles(role.children, path)


def _all_evidence_refs(blueprint: ExpertBlueprint) -> Iterator[str]:
    for claim in blueprint.claims:
        yield from claim.evidence_refs
    for procedure in blueprint.procedures:
        yield from procedure.evidence_refs
    for task in blueprint.tasks:
        yield from task.evidence_refs
    for tool in blueprint.tool_requirements:
        yield from tool.evidence_refs
    for _path, role in _roles(blueprint.roots):
        yield from role.evidence_refs
        for skill in role.skills:
            yield from skill.evidence_refs


__all__ = ["ExpertNetEvaluator", "load_observations"]
