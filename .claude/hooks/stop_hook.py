#!/usr/bin/env python3
"""Ralph Wiggum Stop Hook — keeps Claude working until the task is marked complete.

How it works:
  1. Reads JSON from stdin (Claude Code stop hook payload)
  2. Checks if the current task file has been moved to /Done
  3. If NOT done → exits with code 2 (blocks Claude from stopping, re-injects prompt)
  4. If done (or no task active) → exits with code 0 (allows Claude to stop)

Exit codes:
  0 = Allow Claude to stop
  2 = Block stop, re-inject the original prompt

Reference: https://docs.anthropic.com/en/docs/claude-code/hooks
"""

import json
import os
import sys
from pathlib import Path


def main() -> int:
    # Read hook payload from stdin
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, Exception):
        # If we can't parse the payload, let Claude stop normally
        return 0

    # Check for TASK_COMPLETE promise in Claude's output
    transcript = payload.get("transcript", [])
    for message in transcript:
        content = message.get("content", "")
        if isinstance(content, str) and "<promise>TASK_COMPLETE</promise>" in content:
            return 0
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text", "")
                    if "<promise>TASK_COMPLETE</promise>" in text:
                        return 0

    # Check if active task file has been moved to /Done (file-movement strategy)
    vault_path = os.getenv("VAULT_PATH")
    active_task = os.getenv("RALPH_TASK_FILE")  # set by orchestrator before launching Claude

    if vault_path and active_task:
        done_dir = Path(vault_path) / "Done"
        task_name = Path(active_task).name
        if (done_dir / task_name).exists():
            return 0  # Task completed — allow stop

        # Check max iterations to prevent infinite loops
        iteration_file = Path(vault_path) / ".ralph_iterations"
        max_iterations = int(os.getenv("RALPH_MAX_ITERATIONS", "10"))

        current = 0
        if iteration_file.exists():
            try:
                current = int(iteration_file.read_text().strip())
            except ValueError:
                current = 0

        current += 1
        iteration_file.write_text(str(current))

        if current >= max_iterations:
            # Max iterations reached — allow stop and clean up
            iteration_file.unlink(missing_ok=True)
            print(
                f"[Ralph Wiggum] Max iterations ({max_iterations}) reached. Allowing stop.",
                file=sys.stderr,
            )
            return 0

        # Task not done yet — block stop and re-inject prompt
        print(
            f"[Ralph Wiggum] Task not complete (iteration {current}/{max_iterations}). "
            f"Re-injecting prompt...",
            file=sys.stderr,
        )
        return 2

    # No active task tracking — allow Claude to stop normally
    return 0


if __name__ == "__main__":
    sys.exit(main())
