"""Abstract base class for all AI Employee watchers."""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseWatcher(ABC):
    """Base class for all watchers.

    Subclasses implement check_for_updates() to detect new items,
    then call create_action_file() to write them into the vault.
    """

    def __init__(self, vault_path: str, check_interval: int = 60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / "Needs_Action"
        self.check_interval = check_interval
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        self._validate_vault()

    def _validate_vault(self) -> None:
        needs_action = self.vault_path / "Needs_Action"
        if not needs_action.exists():
            raise FileNotFoundError(
                f"Vault missing /Needs_Action folder. "
                f"Run scripts/setup_vault.py first. Vault: {self.vault_path}"
            )

    @abstractmethod
    def check_for_updates(self) -> list[dict]:
        """Fetch new items since the last check.

        Returns:
            List of dicts, each representing one actionable item.
            Each dict must include at least: 'id', 'type', 'summary'.
        """
        ...

    def create_action_file(self, item: dict) -> Path:
        """Write one item as a Markdown file into /Needs_Action.

        Args:
            item: Dict with keys: id, type, summary, body, metadata (optional).

        Returns:
            Path to the created file.
        """
        item_type = item.get("type", "ITEM").upper()
        item_id = item.get("id", "unknown")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{item_type}_{item_id[:20]}_{timestamp}.md"
        filepath = self.vault_path / "Needs_Action" / filename

        metadata = item.get("metadata", {})
        frontmatter_lines = ["---"]
        frontmatter_lines.append(f"type: {item_type}")
        frontmatter_lines.append(f"source_id: {item_id}")
        frontmatter_lines.append(f"created: {datetime.now(timezone.utc).isoformat()}")
        frontmatter_lines.append(f"status: needs_action")
        for key, value in metadata.items():
            frontmatter_lines.append(f"{key}: {value}")
        frontmatter_lines.append("---")

        content_lines = [
            "\n".join(frontmatter_lines),
            "",
            f"# {item.get('summary', 'New Item')}",
            "",
            item.get("body", ""),
            "",
            "---",
            f"*Created by {self.__class__.__name__} at {datetime.now(timezone.utc).isoformat()}*",
        ]
        content = "\n".join(content_lines)

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create: {filepath}")
            logger.debug(f"[DRY RUN] Content:\n{content}")
            return filepath

        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Created action file: {filepath.name}")
        return filepath

    def _append_to_log(self, entry: dict) -> None:
        """Append a JSON log entry to today's audit log."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.vault_path / "Logs" / f"{today}.json"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        entries = []
        if log_file.exists():
            try:
                entries = json.loads(log_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                entries = []

        entries.append({**entry, "timestamp": datetime.now(timezone.utc).isoformat()})
        log_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def run(self) -> None:
        """Main loop: check for updates every check_interval seconds."""
        mode = "[DRY RUN] " if self.dry_run else ""
        logger.info(f"{mode}{self.__class__.__name__} started. Interval: {self.check_interval}s")

        try:
            while True:
                try:
                    items = self.check_for_updates()
                    if items:
                        logger.info(f"Found {len(items)} new item(s)")
                        for item in items:
                            filepath = self.create_action_file(item)
                            self._append_to_log({
                                "action_type": "item_detected",
                                "actor": self.__class__.__name__,
                                "item_type": item.get("type"),
                                "item_id": item.get("id"),
                                "file": str(filepath.name) if not self.dry_run else "DRY_RUN",
                            })
                    else:
                        logger.debug("No new items found.")
                except Exception as e:
                    logger.error(f"Error in check loop: {e}", exc_info=True)

                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info(f"{self.__class__.__name__} stopped.")
