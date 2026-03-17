#!/usr/bin/env python3
"""Setup the AI Employee Obsidian vault from the vault_template directory.

Usage:
    python scripts/setup_vault.py --vault /path/to/AI_Employee_Vault
    python scripts/setup_vault.py  # uses VAULT_PATH from .env
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TEMPLATE_DIR = Path(__file__).parent.parent / "vault_template"

VAULT_FOLDERS = [
    "Needs_Action",
    "In_Progress",
    "Plans",
    "Pending_Approval",
    "Approved",
    "Rejected",
    "Done",
    "Logs",
    "Accounting",
    "Invoices",
    "Briefings",
    "Inbox",
]


def setup_vault(vault_path: Path, force: bool = False) -> None:
    print(f"\nSetting up AI Employee Vault at: {vault_path}")

    # Create vault root
    vault_path.mkdir(parents=True, exist_ok=True)

    # Create all folders
    for folder in VAULT_FOLDERS:
        folder_path = vault_path / folder
        folder_path.mkdir(exist_ok=True)
        print(f"  [OK] Created folder: {folder}/")

    # Copy template markdown files
    for src_file in TEMPLATE_DIR.rglob("*.md"):
        relative = src_file.relative_to(TEMPLATE_DIR)
        dest_file = vault_path / relative

        # Don't overwrite existing files unless --force
        if dest_file.exists() and not force:
            print(f"  [SKIP] Already exists: {relative} (use --force to overwrite)")
            continue

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
        print(f"  [COPY] {relative}")

    # Create .env if it doesn't exist in project root
    env_file = Path(__file__).parent.parent / ".env"
    env_example = Path(__file__).parent.parent / ".env.example"
    if not env_file.exists() and env_example.exists():
        shutil.copy2(env_example, env_file)
        # Set VAULT_PATH in .env
        content = env_file.read_text()
        content = content.replace(
            "VAULT_PATH=/path/to/your/AI_Employee_Vault",
            f"VAULT_PATH={vault_path}"
        )
        env_file.write_text(content)
        print(f"\n  [ENV] Created .env — update your credentials before running watchers.")
    elif env_file.exists():
        print(f"\n  [ENV] .env already exists — update VAULT_PATH={vault_path} manually if needed.")

    print(f"\nVault setup complete!")
    print(f"\nNext steps:")
    print(f"  1. Open {vault_path} in Obsidian")
    print(f"  2. Edit .env — set your GMAIL_CREDENTIALS_PATH, etc.")
    print(f"  3. Run a watcher: python -m src.watchers.filesystem_watcher")
    print(f"  4. Run the orchestrator: python -m src.orchestrator")
    print(f"  5. Use /process-inbox skill in Claude Code to process items")


def main():
    parser = argparse.ArgumentParser(description="Setup the AI Employee Obsidian vault.")
    parser.add_argument(
        "--vault",
        type=str,
        default=os.getenv("VAULT_PATH", ""),
        help="Path to the vault directory (default: VAULT_PATH from .env)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing vault files",
    )
    args = parser.parse_args()

    if not args.vault:
        print("ERROR: Provide --vault /path/to/vault or set VAULT_PATH in .env")
        sys.exit(1)

    setup_vault(Path(args.vault), force=args.force)


if __name__ == "__main__":
    main()
