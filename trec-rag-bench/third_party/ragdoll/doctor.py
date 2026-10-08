"""`doctor`: verify the Pi binary, agent auth state, and optionally a model."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from ragdoll.config import DoctorConfig, LocalAgentConfig, resolve_thinking
from ragdoll.runner import AGENT_STATE_FILENAMES, default_agent_state_dir, run_prompt


def _resolve_binary(agent_binary: str) -> str | None:
    found = shutil.which(agent_binary)
    if found:
        return found
    path = Path(agent_binary)
    return str(path) if path.exists() else None


async def doctor(config: DoctorConfig) -> None:
    checks_ok = True

    binary = _resolve_binary(config.agent_binary)
    if binary:
        print(f"[ok]   pi binary: {binary}")
    else:
        checks_ok = False
        print(f"[FAIL] pi binary not found: {config.agent_binary!r} (not on PATH and not a file)")

    state_dir = config.agent_state_dir or default_agent_state_dir()
    present = [name for name in AGENT_STATE_FILENAMES if (state_dir / name).is_file()]
    if present:
        print(f"[ok]   agent state: {state_dir} ({', '.join(present)})")
    else:
        checks_ok = False
        print(f"[FAIL] no auth files in {state_dir} (expected one of: {', '.join(AGENT_STATE_FILENAMES)})")

    if config.probe:
        if not binary:
            print("[skip] model probe (no usable binary)")
        else:
            thinking = resolve_thinking(config.model, config.thinking)
            print(f"[..]   probing {config.model} (thinking={thinking}, timeout={config.timeout_seconds:g}s) ...")
            with tempfile.TemporaryDirectory(prefix="ragdoll-doctor-") as tmp:
                result = await run_prompt(
                    task_id="doctor-probe",
                    evaluator="doctor",
                    instruction="Reply with exactly: ok",
                    raw_events_dir=Path(tmp),
                    config=LocalAgentConfig(
                        agent_binary=config.agent_binary,
                        model=config.model,
                        thinking=thinking,
                        timeout_seconds=config.timeout_seconds,
                        agent_state_dir=config.agent_state_dir,
                    ),
                )
            if result["status"] == "completed":
                preview = result["output_text"].replace("\n", " ")[:40]
                print(f"[ok]   model probe: {config.model} responded in {result['elapsed_seconds']}s ({preview!r})")
            else:
                checks_ok = False
                print(f"[FAIL] model probe: {result['error']}")

    print("doctor: PASS" if checks_ok else "doctor: FAIL")
    if not checks_ok:
        raise SystemExit(1)
