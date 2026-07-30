"""Orchestrate Jira → Gherkin → Behave → AI fix loop."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import ai, cucumber
from .jira_client import get_ticket


@dataclass
class PipelineRun:
    id: str
    ticket_key: str
    status: str
    ticket: dict[str, Any] = field(default_factory=dict)
    feature: str = ""
    steps: str = ""
    engine: str = "heuristic"
    iterations: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    workspace: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ticket_key": self.ticket_key,
            "status": self.status,
            "ticket": self.ticket,
            "feature": self.feature,
            "steps": self.steps,
            "engine": self.engine,
            "iterations": self.iterations,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "workspace": self.workspace,
        }


RUNS: dict[str, PipelineRun] = {}


def get_run(run_id: str) -> PipelineRun | None:
    return RUNS.get(run_id)


def list_runs(limit: int = 20) -> list[PipelineRun]:
    runs = sorted(RUNS.values(), key=lambda r: r.created_at, reverse=True)
    return runs[:limit]


def execute_pipeline(
    ticket_key: str,
    *,
    demo_path: Path,
    workspace_root: Path,
    api_key: str = "",
    model: str = "gpt-4o-mini",
    use_ai: bool = True,
    max_iterations: int = 3,
    jira_base_url: str = "",
    jira_email: str = "",
    jira_token: str = "",
    ticket_override: dict[str, Any] | None = None,
) -> PipelineRun:
    run_id = uuid.uuid4().hex[:12]
    run = PipelineRun(id=run_id, ticket_key=ticket_key, status="running")
    RUNS[run_id] = run

    try:
        if ticket_override:
            ticket = ticket_override
        else:
            ticket = get_ticket(
                ticket_key,
                demo_path=demo_path,
                base_url=jira_base_url,
                email=jira_email,
                token=jira_token,
            )
        run.ticket = ticket

        feature, feature_engine = ai.generate_feature(
            ticket, api_key=api_key, model=model, use_ai=use_ai
        )
        run.feature = feature

        steps, steps_engine = ai.generate_steps(
            feature, ticket, api_key=api_key, model=model, use_ai=use_ai
        )
        run.steps = steps
        run.engine = (
            "openai" if "openai" in {feature_engine, steps_engine} else "heuristic"
        )

        ws = cucumber.prepare_workspace(workspace_root, run_id)
        run.workspace = str(ws)
        cucumber.write_feature(ws, feature)
        cucumber.write_steps(ws, steps)

        for attempt in range(1, max(1, max_iterations) + 1):
            result = cucumber.run_behave(ws)
            iteration = {
                "attempt": attempt,
                "passed": result.passed,
                "result": result.to_dict(),
                "steps_snapshot": run.steps,
            }
            run.iterations.append(iteration)
            run.result = result.to_dict()

            if result.passed:
                run.status = "passed"
                run.finished_at = time.time()
                return run

            if attempt >= max_iterations:
                break

            failure_log = (result.stdout or "") + "\n" + (result.stderr or "")
            fixed, fix_engine = ai.generate_steps(
                feature,
                ticket,
                api_key=api_key,
                model=model,
                use_ai=use_ai,
                failure_log=failure_log,
                current_steps=run.steps,
            )
            run.steps = fixed
            if fix_engine == "openai":
                run.engine = "openai"
            cucumber.write_steps(ws, fixed)
            iteration["fixed"] = True

        run.status = "failed"
        run.finished_at = time.time()
        return run

    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error = str(exc)
        run.finished_at = time.time()
        return run
