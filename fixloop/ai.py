from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

from openai import OpenAI


def load_fixloop_config() -> Dict[str, str]:
    cfg_path = Path.home() / ".fixloop" / "config.yaml"
    cfg: Dict[str, str] = {}

    if cfg_path.exists():
        for raw in cfg_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")

    cfg.setdefault("provider", "openai")
    cfg.setdefault("model", "gpt-4o-mini")

    if not cfg.get("openai_api_key"):
        cfg["openai_api_key"] = os.getenv("OPENAI_API_KEY", "").strip()

    return cfg


def _client_and_model() -> tuple[OpenAI, str]:
    cfg = load_fixloop_config()
    api_key = (cfg.get("openai_api_key") or "").strip()
    model = (cfg.get("model") or "gpt-4o-mini").strip()

    if not api_key:
        raise RuntimeError(
            "OpenAI API key not found. Set OPENAI_API_KEY or put openai_api_key in ~/.fixloop/config.yaml"
        )

    return OpenAI(api_key=api_key), model


def ai_test(prompt: str) -> str:
    client, model = _client_and_model()
    resp = client.responses.create(model=model, input=prompt)
    return resp.output_text


def propose_fix_for_file(
    file_path: str,
    file_content: str,
    command: str,
    stderr: str,
    memory_hints: Optional[str] = None,
) -> str:
    """
    Ask the model to return ONLY the corrected full file content (no markdown).
    We compute diff locally and ask user approval.
    """

    client, model = _client_and_model()

    system = (
        "You are FixLoop, a careful debugging assistant.\n"
        "Return ONLY the corrected full file content. No markdown, no code fences, no explanations.\n"
        "Keep changes minimal. Do not rewrite unrelated parts.\n"
        "Prefer small diffs and surgical fixes.\n"
    )

    hints_block = ""
    if memory_hints:
        hints_block = (
            "\n\nLocal memory (previous similar fixes):\n"
            f"{memory_hints}\n"
            "Use these hints ONLY if relevant. Keep changes minimal.\n"
        )

    user = (
        f"Command:\n{command}\n\n"
        f"Error (stderr):\n{stderr}\n\n"
        f"Target file path:\n{file_path}\n\n"
        f"Current file content:\n{file_content}\n"
        f"{hints_block}\n"
        "Task: Fix the runtime error with the smallest reasonable change.\n"
        "Return ONLY the full corrected file content.\n"
    )

    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    out = (resp.output_text or "").replace("\r\n", "\n")

    # Safety: strip accidental fences
    if "```" in out:
        out = out.replace("```python", "").replace("```", "").strip()

    return out
