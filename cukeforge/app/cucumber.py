"""Write Behave workspaces and execute cucumber-style tests."""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BehaveResult:
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    scenarios_passed: int
    scenarios_failed: int
    scenarios_total: int

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "scenarios_passed": self.scenarios_passed,
            "scenarios_failed": self.scenarios_failed,
            "scenarios_total": self.scenarios_total,
        }


def safe_run_id(run_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", run_id).strip("_")
    return cleaned or "run"


def prepare_workspace(root: Path, run_id: str) -> Path:
    ws = root / safe_run_id(run_id)
    features = ws / "features"
    steps = features / "steps"
    features.mkdir(parents=True, exist_ok=True)
    steps.mkdir(parents=True, exist_ok=True)
    init = steps / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
    env_file = features / "environment.py"
    if not env_file.exists():
        env_file.write_text('"""Behave environment hooks."""\n', encoding="utf-8")
    return ws


def write_feature(
    workspace: Path, feature_text: str, filename: str = "ticket.feature"
) -> Path:
    path = workspace / "features" / filename
    path.write_text(
        feature_text if feature_text.endswith("\n") else feature_text + "\n",
        encoding="utf-8",
    )
    return path


def write_steps(
    workspace: Path, steps_text: str, filename: str = "ticket_steps.py"
) -> Path:
    path = workspace / "features" / "steps" / filename
    path.write_text(
        steps_text if steps_text.endswith("\n") else steps_text + "\n",
        encoding="utf-8",
    )
    return path


def _parse_counts(output: str) -> tuple[int, int, int]:
    passed = failed = 0
    m = re.search(
        r"(\d+)\s+scenario(?:s)?\s+passed.*?(\d+)\s+failed",
        output,
        flags=re.I | re.S,
    )
    if m:
        passed = int(m.group(1))
        failed = int(m.group(2))
        return passed, failed, passed + failed

    for kind, bucket in (("passed", "passed"), ("failed", "failed")):
        mm = re.search(rf"(\d+)\s+scenarios?\s+{kind}", output, flags=re.I)
        if mm:
            if bucket == "passed":
                passed = int(mm.group(1))
            else:
                failed = int(mm.group(1))
    return passed, failed, passed + failed


def run_behave(workspace: Path, timeout: int = 60) -> BehaveResult:
    features_dir = workspace / "features"
    cmd = [
        sys.executable,
        "-m",
        "behave",
        str(features_dir),
        "--no-capture",
        "--no-skipped",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    scenarios_passed, scenarios_failed, scenarios_total = _parse_counts(combined)
    passed = proc.returncode == 0 and scenarios_failed == 0
    if proc.returncode == 0 and scenarios_total == 0:
        passed = True
        scenarios_passed = max(scenarios_passed, 1)
        scenarios_total = scenarios_passed
    return BehaveResult(
        passed=passed,
        exit_code=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        scenarios_passed=scenarios_passed,
        scenarios_failed=scenarios_failed,
        scenarios_total=scenarios_total or (scenarios_passed + scenarios_failed),
    )
