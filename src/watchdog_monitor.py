"""Watchdog Monitor — health-checks and auto-restarts failed processes."""

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

MONITORED_PROCESSES = [
    {
        "name": "gmail_watcher",
        "command": ["python", "-m", "src.watchers.gmail_watcher"],
        "pid_file": ".pids/gmail_watcher.pid",
    },
    {
        "name": "filesystem_watcher",
        "command": ["python", "-m", "src.watchers.filesystem_watcher"],
        "pid_file": ".pids/filesystem_watcher.pid",
    },
    {
        "name": "orchestrator",
        "command": ["python", "-m", "src.orchestrator"],
        "pid_file": ".pids/orchestrator.pid",
    },
]

CHECK_INTERVAL = int(os.getenv("WATCHDOG_CHECK_INTERVAL", "60"))


def is_process_alive(pid: int) -> bool:
    """Check if a PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def start_process(proc_config: dict) -> int | None:
    """Start a process and record its PID."""
    pid_file = Path(proc_config["pid_file"])
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        proc = subprocess.Popen(
            proc_config["command"],
            stdout=open(f".logs/{proc_config['name']}.log", "a"),
            stderr=subprocess.STDOUT,
        )
        pid_file.write_text(str(proc.pid))
        logger.info(f"Started {proc_config['name']} (PID {proc.pid})")
        return proc.pid
    except Exception as e:
        logger.error(f"Failed to start {proc_config['name']}: {e}")
        return None


def check_and_restart(proc_config: dict) -> None:
    """Verify the process is alive; restart if not."""
    pid_file = Path(proc_config["pid_file"])

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            if is_process_alive(pid):
                logger.debug(f"{proc_config['name']} OK (PID {pid})")
                return
            logger.warning(f"{proc_config['name']} (PID {pid}) is dead — restarting...")
        except ValueError:
            logger.warning(f"Invalid PID file for {proc_config['name']} — restarting...")
    else:
        logger.info(f"{proc_config['name']} not started — starting now...")

    start_process(proc_config)


def run_watchdog() -> None:
    Path(".logs").mkdir(exist_ok=True)
    logger.info(f"Watchdog Monitor started. Check interval: {CHECK_INTERVAL}s")

    try:
        while True:
            for proc in MONITORED_PROCESSES:
                try:
                    check_and_restart(proc)
                except Exception as e:
                    logger.error(f"Error checking {proc['name']}: {e}")
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Watchdog Monitor stopped.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_watchdog()
