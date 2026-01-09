from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class RunResult:
    cmd: str
    returncode: int
    stdout: str
    stderr: str


def run_command(cmd: str, cwd: str | None = None) -> RunResult:
    """
    Runs a shell command and captures stdout/stderr.
    """
    p = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    return RunResult(cmd=cmd, returncode=p.returncode, stdout=p.stdout or "", stderr=p.stderr or "")
