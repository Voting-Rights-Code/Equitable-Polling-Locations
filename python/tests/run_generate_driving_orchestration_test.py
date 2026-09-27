"""Unit tests for generate_driving_distances_cli orchestration in run.py.

Verifies that the buffer-prep step (build_buffered_extract_cli) is scheduled
before ORS is booted (ors_up_cli), using monkeypatching to avoid any real
subprocess or Docker invocations.
"""

import sys
import importlib.util
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("run_module", REPO_ROOT / "run.py")
run_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_module)


def test_buffer_prep_runs_before_ors_up(monkeypatch):
    """build_buffered_extract_cli run_command must precede the ors_up subprocess call."""
    calls = []
    monkeypatch.setattr(run_module, "IN_CONTAINER", False)
    monkeypatch.setattr(run_module, "_ors_is_healthy", lambda: False)
    monkeypatch.setattr(
        run_module,
        "run_command",
        lambda cmd, **k: calls.append(("run_command", tuple(cmd))),
    )
    monkeypatch.setattr(
        run_module.subprocess,
        "run",
        lambda cmd, **k: calls.append(("subprocess", tuple(cmd))),
    )
    # _load_ors_setup_helpers is only called when --testing is absent; provide a
    # stub anyway so the test is robust if control flow ever changes.
    monkeypatch.setattr(
        run_module,
        "_load_ors_setup_helpers",
        lambda: (lambda loc: "georgia", lambda path: "X_GA"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["run.py", "generate_driving_distances_cli", "--testing",
         "-l", "cfg.yaml"],
    )
    run_module.main()

    # Collect the command tuples in call order.
    labels = [cmd for (_, cmd) in calls]
    buffer_index = next(
        i
        for i, cmd in enumerate(labels)
        if "build_buffered_extract_cli" in " ".join(cmd)
    )
    ors_up_index = next(
        i
        for i, cmd in enumerate(labels)
        if "ors_up_cli" in " ".join(map(str, cmd))
    )
    assert buffer_index < ors_up_index, (
        f"build_buffered_extract_cli (call {buffer_index}) must run before "
        f"ors_up_cli (call {ors_up_index}); full call list: {labels}"
    )
