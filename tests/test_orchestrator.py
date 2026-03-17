"""Tests for the Orchestrator vault state machine."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.orchestrator import Orchestrator


@pytest.fixture
def vault(tmp_path):
    """Full vault structure required by Orchestrator."""
    for folder in ["Needs_Action", "In_Progress", "Pending_Approval",
                   "Approved", "Rejected", "Done", "Logs"]:
        (tmp_path / folder).mkdir()
    (tmp_path / "Dashboard.md").write_text("# Dashboard\n\n## Live Status\n\nplaceholder\n")
    return tmp_path


@pytest.fixture
def orc(vault, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("VAULT_PATH", str(vault))
    return Orchestrator(str(vault))


# ------------------------------------------------------------------
# Vault validation
# ------------------------------------------------------------------

def test_missing_vault_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="Needs_Action"):
        Orchestrator(str(tmp_path))


# ------------------------------------------------------------------
# State transitions
# ------------------------------------------------------------------

def test_needs_action_claimed_by_move(vault, orc, monkeypatch):
    monkeypatch.setattr(orc, "_trigger_claude", lambda f: None)

    task = vault / "Needs_Action" / "EMAIL_test_001.md"
    task.write_text("---\ntype: EMAIL\nstatus: needs_action\n---\n# Test Task\n")

    orc._process_needs_action()

    assert not task.exists(), "File should leave /Needs_Action"
    in_progress = vault / "In_Progress" / "orchestrator" / "EMAIL_test_001.md"
    assert in_progress.exists(), "File should be in /In_Progress/orchestrator"


def test_approved_action_moves_to_done(vault, orc):
    approved = vault / "Approved" / "EMAIL_send_001.md"
    approved.write_text("---\naction_type: email_send\nto: test@example.com\nsubject: Hello\n---\n")

    orc._process_approved()

    assert not approved.exists()
    done = vault / "Done" / "EMAIL_send_001.md"
    assert done.exists()


def test_rejected_action_archived_to_done(vault, orc):
    rejected = vault / "Rejected" / "EMAIL_spam_001.md"
    rejected.write_text("---\ntype: EMAIL\nstatus: rejected\n---\n")

    orc._process_rejected()

    assert not rejected.exists()
    done = vault / "Done" / "REJECTED_EMAIL_spam_001.md"
    assert done.exists()


# ------------------------------------------------------------------
# Dashboard update
# ------------------------------------------------------------------

def test_dashboard_updated_with_counts(vault, orc, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")

    (vault / "Needs_Action" / "item1.md").write_text("test")
    (vault / "Needs_Action" / "item2.md").write_text("test")
    (vault / "Pending_Approval" / "approval1.md").write_text("test")

    orc._update_dashboard()

    content = (vault / "Dashboard.md").read_text()
    assert "Needs Action | 2" in content
    assert "Pending Approval | 1" in content


def test_dashboard_not_written_in_dry_run(vault, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    orc = Orchestrator(str(vault))
    original = (vault / "Dashboard.md").read_text()

    orc._update_dashboard()

    assert (vault / "Dashboard.md").read_text() == original


# ------------------------------------------------------------------
# Audit logging
# ------------------------------------------------------------------

def test_log_transition_creates_json(vault, orc):
    orc._log_transition("test_file.md", "needs_action", "in_progress")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = vault / "Logs" / f"{today}.json"
    assert log_file.exists()

    entries = json.loads(log_file.read_text())
    assert len(entries) == 1
    assert entries[0]["from_state"] == "needs_action"
    assert entries[0]["to_state"] == "in_progress"
    assert entries[0]["file"] == "test_file.md"


def test_log_appends_multiple_transitions(vault, orc):
    orc._log_transition("a.md", "needs_action", "in_progress")
    orc._log_transition("b.md", "approved", "done")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = json.loads((vault / "Logs" / f"{today}.json").read_text())
    assert len(entries) == 2


# ------------------------------------------------------------------
# Frontmatter parsing
# ------------------------------------------------------------------

def test_read_frontmatter_field(vault, orc, tmp_path):
    md = tmp_path / "test.md"
    md.write_text("---\naction_type: email_send\nto: alice@example.com\n---\n# Body\n")

    assert orc._read_frontmatter_field(md, "action_type") == "email_send"
    assert orc._read_frontmatter_field(md, "to") == "alice@example.com"
    assert orc._read_frontmatter_field(md, "missing") is None


# ------------------------------------------------------------------
# Dry run — no files moved
# ------------------------------------------------------------------

def test_dry_run_no_files_moved(vault, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    orc = Orchestrator(str(vault))

    task = vault / "Needs_Action" / "EMAIL_dryrun.md"
    task.write_text("---\ntype: EMAIL\n---\n# Dry run task\n")

    orc._process_needs_action()

    assert task.exists()
