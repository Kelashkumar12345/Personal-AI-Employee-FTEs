"""Filesystem Watcher — monitors a drop folder and writes action files to the vault.

Use this watcher to test the full pipeline without external APIs.
Drop any file into the configured INBOX_PATH and it will appear in /Needs_Action.
"""

import logging
import os
import shutil
import time
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .base_watcher import BaseWatcher

logger = logging.getLogger(__name__)


class _DropFolderHandler(FileSystemEventHandler):
    """Watchdog event handler that queues newly created files."""

    def __init__(self):
        self.new_files: list[Path] = []

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        # Skip hidden files and temp files created by editors
        if path.name.startswith(".") or path.suffix in (".tmp", ".part", ".swp"):
            return
        logger.debug(f"Drop folder: new file detected: {path.name}")
        self.new_files.append(path)


class FilesystemWatcher(BaseWatcher):
    """Watches a local drop folder for new files.

    Great for:
    - Testing the vault pipeline without API credentials
    - Drag-and-drop document intake (contracts, invoices, receipts)
    - Any file-based workflow triggers

    Configuration (.env):
        INBOX_PATH: folder to watch for dropped files (default: ./Inbox)
        FILESYSTEM_CHECK_INTERVAL: polling interval in seconds (default: 10)
    """

    def __init__(self, vault_path: str, inbox_path: str | None = None):
        check_interval = int(os.getenv("FILESYSTEM_CHECK_INTERVAL", "10"))
        super().__init__(vault_path, check_interval)

        self.inbox_path = Path(
            inbox_path or os.getenv("INBOX_PATH", str(self.vault_path / "Inbox"))
        )
        self.inbox_path.mkdir(parents=True, exist_ok=True)

        self._handler = _DropFolderHandler()
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.inbox_path), recursive=False)
        self._observer.start()
        logger.info(f"FilesystemWatcher watching: {self.inbox_path}")

    def _classify_file(self, path: Path) -> str:
        """Guess item type from file extension."""
        ext = path.suffix.lower()
        mapping = {
            ".pdf": "DOCUMENT",
            ".png": "IMAGE",
            ".jpg": "IMAGE",
            ".jpeg": "IMAGE",
            ".csv": "DATA",
            ".xlsx": "DATA",
            ".xls": "DATA",
            ".docx": "DOCUMENT",
            ".txt": "NOTE",
            ".md": "NOTE",
        }
        return mapping.get(ext, "FILE")

    def check_for_updates(self) -> list[dict]:
        """Return items for any new files dropped into the inbox folder."""
        new_files = self._handler.new_files.copy()
        self._handler.new_files.clear()

        items = []
        for path in new_files:
            if not path.exists():
                continue
            item_type = self._classify_file(path)
            stat = path.stat()

            # Copy the actual file into /Needs_Action/ so Claude can access it
            if not self.dry_run:
                dest = self.needs_action / f"FILE_{path.name}"
                shutil.copy2(path, dest)
                logger.info(f"Copied {path.name} → Needs_Action/FILE_{path.name}")

            items.append({
                "id": path.stem[:20],
                "type": item_type,
                "summary": f"New {item_type.lower()} dropped: {path.name}",
                "body": (
                    f"**File:** {path.name}\n"
                    f"**Path:** `{self.needs_action / ('FILE_' + path.name)}`\n"
                    f"**Size:** {stat.st_size:,} bytes\n"
                    f"**Type:** {item_type}\n\n"
                    f"Review this file and determine the appropriate action."
                ),
                "metadata": {
                    "filename": path.name,
                    "original_path": str(path),
                    "file_size": stat.st_size,
                    "file_type": item_type,
                },
            })
        return items

    def run(self) -> None:
        """Run with graceful shutdown on KeyboardInterrupt."""
        try:
            super().run()
        finally:
            self._observer.stop()
            self._observer.join()
            logger.info("FilesystemWatcher stopped.")


def main():
    import sys
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    vault = os.getenv("VAULT_PATH")
    if not vault:
        print("ERROR: Set VAULT_PATH in .env")
        sys.exit(1)

    FilesystemWatcher(vault).run()


if __name__ == "__main__":
    main()
