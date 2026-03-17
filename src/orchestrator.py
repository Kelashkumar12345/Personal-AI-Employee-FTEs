"""Orchestrator — watches the vault and manages state transitions.

Responsibilities:
  - Monitor /Needs_Action for new items (triggers Claude processing)
  - Monitor /Approved for items ready to execute (triggers MCP actions)
  - Update Dashboard.md with current vault status
  - Log all state transitions to /Logs/YYYY-MM-DD.json
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class Orchestrator:
    """Core orchestrator that manages the vault state machine.

    State machine: /Needs_Action → /In_Progress/orchestrator
                  → /Pending_Approval (by Claude)
                  → /Approved (by human)  → execute MCP → /Done
                  → /Rejected (by human) → /Done
    """

    AGENT_NAME = "orchestrator"
    POLL_INTERVAL = int(os.getenv("ORCHESTRATOR_POLL_INTERVAL", "15"))

    def __init__(self, vault_path: str):
        self.vault = Path(vault_path)
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        self._validate_vault()

    def _validate_vault(self) -> None:
        required = ["Needs_Action", "Approved", "Done", "Logs"]
        missing = [d for d in required if not (self.vault / d).exists()]
        if missing:
            raise FileNotFoundError(
                f"Vault missing folders: {missing}. Run scripts/setup_vault.py first."
            )

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        mode = "[DRY RUN] " if self.dry_run else ""
        logger.info(f"{mode}Orchestrator started. Vault: {self.vault}")

        while True:
            try:
                self._process_needs_action()
                self._process_approved()
                self._process_rejected()
                self._update_dashboard()
            except Exception as e:
                logger.error(f"Orchestrator loop error: {e}", exc_info=True)

            time.sleep(self.POLL_INTERVAL)

    # ------------------------------------------------------------------
    # Stage handlers
    # ------------------------------------------------------------------

    def _process_needs_action(self) -> None:
        """Move unclaimed items to /In_Progress and trigger Claude."""
        in_progress_dir = self.vault / "In_Progress" / self.AGENT_NAME
        in_progress_dir.mkdir(parents=True, exist_ok=True)

        for md_file in (self.vault / "Needs_Action").glob("*.md"):
            if self.dry_run:
                logger.info(f"[DRY RUN] Would claim and process: {md_file.name}")
                continue

            # Claim by move
            dest = in_progress_dir / md_file.name
            md_file.rename(dest)
            logger.info(f"Claimed: {md_file.name} → In_Progress/{self.AGENT_NAME}/")
            self._log_transition(md_file.name, "needs_action", "in_progress")

            # Trigger Claude Code to process this task
            self._trigger_claude(dest)

    def _trigger_claude(self, task_file: Path) -> None:
        """Invoke Claude Code to process a task file."""
        prompt = (
            f"Read the task file at {task_file} and process it according to the "
            f"Company_Handbook.md and Business_Goals.md in the vault at {self.vault}. "
            f"If the action requires human approval, create an approval request in "
            f"{self.vault}/Pending_Approval/. Otherwise move it to {self.vault}/Done/ "
            f"after completing the task. Log all actions."
        )
        logger.info(f"Triggering Claude for: {task_file.name}")
        try:
            subprocess.Popen(
                ["claude", "-p", prompt, "--no-interactive"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.warning("Claude Code not found in PATH. Install with: npm install -g @anthropic-ai/claude-code")

    def _process_approved(self) -> None:
        """Execute approved actions and move to /Done."""
        approved_dir = self.vault / "Approved"
        done_dir = self.vault / "Done"
        done_dir.mkdir(parents=True, exist_ok=True)

        for md_file in approved_dir.glob("*.md"):
            logger.info(f"Approved action ready: {md_file.name}")
            action_type = self._read_frontmatter_field(md_file, "action_type")

            if self.dry_run:
                logger.info(f"[DRY RUN] Would execute {action_type} from: {md_file.name}")
                continue

            success = self._dispatch_action(md_file, action_type)

            dest = done_dir / md_file.name
            md_file.rename(dest)
            self._log_transition(
                md_file.name, "approved", "done",
                extra={"action_type": action_type, "result": "success" if success else "failed"},
            )

    def _process_rejected(self) -> None:
        """Archive rejected items to /Done."""
        rejected_dir = self.vault / "Rejected"
        done_dir = self.vault / "Done"
        done_dir.mkdir(parents=True, exist_ok=True)

        for md_file in rejected_dir.glob("*.md"):
            if self.dry_run:
                logger.info(f"[DRY RUN] Would archive rejected: {md_file.name}")
                continue
            dest = done_dir / f"REJECTED_{md_file.name}"
            md_file.rename(dest)
            logger.info(f"Archived rejected: {md_file.name}")
            self._log_transition(md_file.name, "rejected", "done")

    # ------------------------------------------------------------------
    # Action dispatcher
    # ------------------------------------------------------------------

    def _dispatch_action(self, task_file: Path, action_type: str | None) -> bool:
        """Route an approved action to the correct MCP handler.

        Extend this method to add new action types.
        """
        logger.info(f"Dispatching action_type={action_type} for {task_file.name}")

        if action_type == "email_send":
            return self._action_email_send(task_file)
        elif action_type == "file_create":
            return self._action_file_create(task_file)
        else:
            logger.warning(f"Unknown action_type '{action_type}' — marking as done without action.")
            return True

    def _action_email_send(self, task_file: Path) -> bool:
        """Placeholder: invoke email-mcp to send an email."""
        to = self._read_frontmatter_field(task_file, "to")
        subject = self._read_frontmatter_field(task_file, "subject")
        logger.info(f"[ACTION] Would send email to {to} — subject: {subject}")
        # TODO: invoke email-mcp server here
        return True

    def _action_file_create(self, task_file: Path) -> bool:
        """Placeholder: create a file as instructed."""
        logger.info(f"[ACTION] file_create for {task_file.name}")
        # TODO: implement file creation action
        return True

    # ------------------------------------------------------------------
    # Dashboard update
    # ------------------------------------------------------------------

    def _update_dashboard(self) -> None:
        """Rewrite Dashboard.md with current vault counts."""
        counts = {
            "needs_action": len(list((self.vault / "Needs_Action").glob("*.md"))),
            "in_progress": sum(
                len(list(d.glob("*.md")))
                for d in (self.vault / "In_Progress").iterdir()
                if d.is_dir()
            ) if (self.vault / "In_Progress").exists() else 0,
            "pending_approval": len(list((self.vault / "Pending_Approval").glob("*.md"))),
            "approved": len(list((self.vault / "Approved").glob("*.md"))),
            "done_today": len([
                f for f in (self.vault / "Done").glob("*.md")
                if datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).date()
                == datetime.now(timezone.utc).date()
            ]) if (self.vault / "Done").exists() else 0,
        }

        dashboard = self.vault / "Dashboard.md"
        if not dashboard.exists():
            return

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        status_block = (
            f"\n## Live Status — {now}\n\n"
            f"| Folder | Items |\n"
            f"|--------|-------|\n"
            f"| Needs Action | {counts['needs_action']} |\n"
            f"| In Progress | {counts['in_progress']} |\n"
            f"| Pending Approval | {counts['pending_approval']} |\n"
            f"| Approved (queued) | {counts['approved']} |\n"
            f"| Done (today) | {counts['done_today']} |\n"
        )

        content = dashboard.read_text(encoding="utf-8")
        marker = "## Live Status"
        if marker in content:
            content = content[: content.index(marker)] + status_block
        else:
            content += status_block

        if not self.dry_run:
            dashboard.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_frontmatter_field(self, path: Path, field: str) -> str | None:
        """Extract a single YAML frontmatter field from a Markdown file."""
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            in_fm = False
            for line in lines:
                if line.strip() == "---":
                    in_fm = not in_fm
                    continue
                if in_fm and line.startswith(f"{field}:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return None

    def _log_transition(self, filename: str, from_state: str, to_state: str, extra: dict = None) -> None:
        """Append a state-transition entry to today's audit log."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.vault / "Logs" / f"{today}.json"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        entries = []
        if log_file.exists():
            try:
                entries = json.loads(log_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                entries = []

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": "state_transition",
            "actor": self.AGENT_NAME,
            "file": filename,
            "from_state": from_state,
            "to_state": to_state,
        }
        if extra:
            entry.update(extra)
        entries.append(entry)
        log_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def main():
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    vault = os.getenv("VAULT_PATH")
    if not vault:
        print("ERROR: Set VAULT_PATH in .env")
        sys.exit(1)

    Orchestrator(vault).run()


if __name__ == "__main__":
    main()
