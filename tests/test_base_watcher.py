"""Tests for BaseWatcher and FilesystemWatcher."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.watchers.base_watcher import BaseWatcher
from src.watchers.filesystem_watcher import FilesystemWatcher


class ConcreteWatcher(BaseWatcher):
    """Minimal concrete implementation for testing BaseWatcher."""

    def check_for_updates(self):
        return []


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "Needs_Action").mkdir()
    (tmp_path / "Logs").mkdir()
    return tmp_path


@pytest.fixture
def watcher(vault, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    return ConcreteWatcher(str(vault))


# ------------------------------------------------------------------
# create_action_file
# ------------------------------------------------------------------

def test_create_action_file_dry_run(vault, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    w = ConcreteWatcher(str(vault))
    item = {"id": "abc123", "type": "EMAIL", "summary": "Test email", "body": "Hello"}
    path = w.create_action_file(item)
    assert not path.exists()


def test_create_action_file_live(vault, watcher):
    item = {"id": "abc123", "type": "EMAIL", "summary": "Test email", "body": "Hello"}
    path = watcher.create_action_file(item)
    assert path.exists()
    assert path.suffix == ".md"


def test_action_file_has_frontmatter(vault, watcher):
    item = {
        "id": "msg001",
        "type": "EMAIL",
        "summary": "Invoice received",
        "body": "Please find attached.",
        "metadata": {"from": "client@example.com", "priority": "high"},
    }
    path = watcher.create_action_file(item)
    content = path.read_text()
    assert "---" in content
    assert "type: EMAIL" in content
    assert "source_id: msg001" in content
    assert "from: client@example.com" in content


# ------------------------------------------------------------------
# Audit logging
# ------------------------------------------------------------------

def test_log_appends_entries(vault, watcher):
    watcher._append_to_log({"action_type": "test", "actor": "watcher"})
    watcher._append_to_log({"action_type": "test2", "actor": "watcher"})

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = vault / "Logs" / f"{today}.json"
    entries = json.loads(log_file.read_text())
    assert len(entries) == 2


# ------------------------------------------------------------------
# Vault validation
# ------------------------------------------------------------------

def test_validate_vault_missing_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    with pytest.raises(FileNotFoundError, match="Needs_Action"):
        ConcreteWatcher(str(tmp_path))


# ------------------------------------------------------------------
# FilesystemWatcher file classification
# ------------------------------------------------------------------

def test_filesystem_watcher_classifies_files(vault, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    fw = FilesystemWatcher(str(vault))

    assert fw._classify_file(Path("doc.pdf")) == "DOCUMENT"
    assert fw._classify_file(Path("photo.jpg")) == "IMAGE"
    assert fw._classify_file(Path("data.csv")) == "DATA"
    assert fw._classify_file(Path("note.txt")) == "NOTE"
    assert fw._classify_file(Path("unknown.xyz")) == "FILE"

    fw._observer.stop()
    fw._observer.join()
