"""Tests for the Ralph Wiggum Stop Hook."""

import json
import sys
from pathlib import Path

import pytest


def run_hook(payload: dict, env: dict = None, monkeypatch=None) -> int:
    """Helper: run stop_hook.main() with given payload and env."""
    import importlib
    import io

    if monkeypatch:
        for key, value in (env or {}).items():
            monkeypatch.setenv(key, value)

    hook_module = importlib.import_module(".claude.hooks.stop_hook".replace(".", "_"))

    # Reload to pick up env changes
    import importlib
    import sys
    if "claude_hooks_stop_hook" in sys.modules:
        del sys.modules["claude_hooks_stop_hook"]

    # Direct import
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "stop_hook",
        Path(".claude/hooks/stop_hook.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    original_stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps(payload))
    try:
        return mod.main()
    finally:
        sys.stdin = original_stdin


def load_hook():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "stop_hook",
        Path(".claude/hooks/stop_hook.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_allows_stop_on_task_complete_promise(monkeypatch):
    mod = load_hook()
    import io
    payload = {
        "transcript": [
            {"role": "assistant", "content": "Done! <promise>TASK_COMPLETE</promise>"}
        ]
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert mod.main() == 0


def test_blocks_stop_without_promise(monkeypatch, tmp_path):
    mod = load_hook()
    import io
    payload = {"transcript": [{"role": "assistant", "content": "Still working..."}]}
    monkeypatch.setenv("VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("RALPH_TASK_FILE", str(tmp_path / "task.md"))
    monkeypatch.setenv("RALPH_MAX_ITERATIONS", "5")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    result = mod.main()
    assert result == 2


def test_allows_stop_on_invalid_payload(monkeypatch):
    mod = load_hook()
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert mod.main() == 0


def test_allows_stop_on_empty_transcript(monkeypatch):
    mod = load_hook()
    import io
    payload = {"transcript": []}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert mod.main() == 0


def test_blocks_stop_when_task_not_done(monkeypatch, tmp_path):
    mod = load_hook()
    import io
    payload = {"transcript": []}
    task_file = tmp_path / "EMAIL_task.md"
    task_file.write_text("test")
    monkeypatch.setenv("VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("RALPH_TASK_FILE", str(task_file))
    monkeypatch.setenv("RALPH_MAX_ITERATIONS", "10")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    result = mod.main()
    assert result == 2


def test_allows_stop_when_task_in_done(monkeypatch, tmp_path):
    mod = load_hook()
    import io
    done_dir = tmp_path / "Done"
    done_dir.mkdir()
    (done_dir / "EMAIL_task.md").write_text("done")
    payload = {"transcript": []}
    monkeypatch.setenv("VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("RALPH_TASK_FILE", str(tmp_path / "EMAIL_task.md"))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert mod.main() == 0


def test_allows_stop_at_max_iterations(monkeypatch, tmp_path):
    mod = load_hook()
    import io
    iter_file = tmp_path / ".ralph_iterations"
    iter_file.write_text("9")
    task_file = tmp_path / "task.md"
    task_file.write_text("test")
    payload = {"transcript": []}
    monkeypatch.setenv("VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("RALPH_TASK_FILE", str(task_file))
    monkeypatch.setenv("RALPH_MAX_ITERATIONS", "10")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    result = mod.main()
    assert result == 0
