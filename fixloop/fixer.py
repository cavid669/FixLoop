from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .runner import run_command
from .ai import propose_fix_for_file


@dataclass
class FixOutcome:
    ok: bool
    message: str


def _extract_primary_py_file(stderr: str) -> Optional[str]:
    """
    Extract last referenced .py file from a Python traceback.
    """
    matches = re.findall(r'File "([^"]+\.py)"', stderr)
    if not matches:
        return None
    return matches[-1]


def _unified_diff(old: str, new: str, path: str) -> str:
    import difflib
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff)


# ---------------- SAFETY GATES ----------------

def _count_changed_lines(diff_text: str) -> int:
    """
    Count actual changed lines (+ / -) ignoring diff headers.
    """
    n = 0
    for line in diff_text.splitlines():
        if line.startswith(("+++ ", "--- ", "@@")):
            continue
        if line.startswith("+") or line.startswith("-"):
            n += 1
    return n


def _gate_large_diff(diff_text: str, max_changed_lines: int) -> Tuple[bool, str]:
    changed = _count_changed_lines(diff_text)
    if changed > max_changed_lines:
        return (
            False,
            f"❌ Safety gate: diff too large "
            f"({changed} changed lines > {max_changed_lines}).",
        )
    return True, ""


def _ask_approval(diff_text: str) -> bool:
    print("\n--- Proposed diff (diff-only) ---")
    print(diff_text if diff_text.strip() else "(no changes)")
    print("--- End diff ---\n")
    ans = input("Apply this patch? [y/N]: ").strip().lower()
    return ans in ("y", "yes")


# ---------------- CORE FIX LOOP ----------------

def fix_loop(
    cmd: str,
    verify_cmd: Optional[str] = None,
    yes: bool = False,
    max_iters: int = 1,
    max_changed_lines: int = 60,
) -> FixOutcome:
    """
    FixLoop MVP:
      1) Run command
      2) Capture error
      3) Ask AI for minimal fix (full file content)
      4) Show diff-only
      5) Safety gate (max diff lines)
      6) Apply (with approval)
      7) Re-run + optional verify
    """

    for attempt in range(1, max_iters + 1):
        result = run_command(cmd)

        # SUCCESS
        if result.returncode == 0:
            if verify_cmd:
                verify = run_command(verify_cmd)
                if verify.returncode != 0:
                    return FixOutcome(
                        False,
                        f"❌ Verify failed.\n\nSTDOUT:\n{verify.stdout}\n\nSTDERR:\n{verify.stderr}",
                    )
                return FixOutcome(True, "✅ Command succeeded (and verify passed).")
            return FixOutcome(True, "✅ Command succeeded.")

        # FAILURE
        target_file = (
            _extract_primary_py_file(result.stderr)
            or _extract_primary_py_file(result.stdout)
        )

        if not target_file:
            return FixOutcome(
                False,
                f"❌ Command failed, but no .py file found in traceback.\n\nSTDERR:\n{result.stderr}",
            )

        p = Path(target_file)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()

        if not p.exists():
            return FixOutcome(False, f"❌ File not found: {p}")

        old_content = p.read_text(encoding="utf-8")

        new_content = propose_fix_for_file(
            file_path=str(p),
            file_content=old_content,
            command=cmd,
            stderr=result.stderr,
        )

        diff_text = _unified_diff(old_content, new_content, str(p).replace("\\", "/"))

        # SAFETY GATE
        ok_gate, gate_msg = _gate_large_diff(diff_text, max_changed_lines)
        if not ok_gate:
            print("\n--- Proposed diff (diff-only) ---")
            print(diff_text if diff_text.strip() else "(no changes)")
            print("--- End diff ---\n")
            print(gate_msg)
            # Force approval even if --yes
            if not _ask_approval(diff_text):
                return FixOutcome(False, "⏹️ Patch blocked by safety gate.")

        # NORMAL APPROVAL
        if not yes:
            if not _ask_approval(diff_text):
                return FixOutcome(False, "⏹️ Patch not applied (user declined).")

        # APPLY PATCH
        p.write_text(new_content, encoding="utf-8")

        # RE-RUN
        rerun = run_command(cmd)
        if rerun.returncode == 0:
            if verify_cmd:
                verify = run_command(verify_cmd)
                if verify.returncode != 0:
                    return FixOutcome(
                        False,
                        f"❌ Verify failed after fix.\n\nSTDERR:\n{verify.stderr}",
                    )
            return FixOutcome(True, f"✅ Fixed on attempt {attempt}.")

        if attempt == max_iters:
            return FixOutcome(
                False,
                f"❌ Patch applied but command still fails.\n\nSTDERR:\n{rerun.stderr}",
            )

    return FixOutcome(False, "❌ FixLoop exited unexpectedly.")
