# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Personal AI Employee (Digital FTE)** — An autonomous agent system that proactively manages personal affairs (Gmail, WhatsApp, Banking) and business operations (Social Media, Payments, Projects) using Claude Code as the reasoning engine and Obsidian as the local-first dashboard.

Core loop: **Perception → Reasoning → Action**
1. Python Watchers detect changes → write `.md` files to `/Needs_Action/`
2. Claude reads vault, plans, writes to `/Plans/` and `/Pending_Approval/`
3. Human approves → Orchestrator triggers MCP action → moves files to `/Done/`

## Tech Stack

- **Brain:** Claude Code (with Ralph Wiggum Stop hook for continuous iteration)
- **Memory/GUI:** Obsidian v1.10.6+ — local Markdown vault as the dashboard
- **Watchers:** Python 3.13+ scripts using `watchdog`, `playwright`, Gmail API
- **Hands:** MCP servers (`filesystem`, `email-mcp`, `browser-mcp`, `calendar-mcp`, `slack-mcp`)
- **Process Management:** PM2 (`npm install -g pm2`) for daemonizing Python scripts
- **Task Scheduling:** cron (Linux/macOS) or Windows Task Scheduler
- **Orchestration:** `Orchestrator.py` + `Watchdog.py`

## Setup Commands

```bash
# Verify prerequisites
claude --version
python --version   # 3.13+
node --version     # v24+ LTS

# Python environment (use uv)
uv init
uv add google-auth google-auth-oauthlib google-api-python-client
uv add playwright watchdog python-dotenv

# Process management
npm install -g pm2
pm2 start gmail_watcher.py --interpreter python3
pm2 save && pm2 startup

# Start Ralph loop for continuous task execution
/ralph-loop "Process all files in /Needs_Action" \
  --completion-promise "TASK_COMPLETE" \
  --max-iterations 10
```

## Obsidian Vault Structure

All state is persisted as Markdown. The vault is the source of truth.

```
/AI_Employee_Vault/
  ├── Dashboard.md              # Real-time summary (balance, pending, activity)
  ├── Company_Handbook.md       # Rules of engagement, decision thresholds
  ├── Business_Goals.md         # Quarterly objectives, key metrics
  ├── /Needs_Action/            # Incoming items from Watchers
  ├── /In_Progress/<agent>/     # Claimed by first agent (claim-by-move rule)
  ├── /Plans/                   # Step-by-step plans with checkboxes
  ├── /Pending_Approval/        # Sensitive actions awaiting human approval
  ├── /Approved/                # Approved → Orchestrator triggers MCP
  ├── /Rejected/                # Rejected (audit trail)
  ├── /Done/                    # Completed tasks
  ├── /Logs/                    # YYYY-MM-DD.json audit logs (90-day minimum)
  ├── /Accounting/              # Transactions, rates, Current_Month.md
  ├── /Invoices/                # Generated PDFs
  └── /Briefings/               # Weekly CEO briefings
```

**File-based state machine:** `/Needs_Action` → `/In_Progress` → `/Pending_Approval` → `/Approved` → `/Done`

## Key Architectural Patterns

### Ralph Wiggum Stop Hook
Intercepts Claude's exit, checks if current task file exists in `/Done`. If not — blocks exit and re-injects the prompt. Prevents premature termination of long-running tasks.

### Human-in-the-Loop (HITL)
Claude never directly executes sensitive actions. It creates an approval file in `/Pending_Approval/` with frontmatter metadata (`action_type`, `target`, `amount`, `reason`). Human moves to `/Approved/`; Orchestrator watches and triggers MCP.

**Required approval for:** payments over threshold, emails to new recipients, legal/medical matters, irreversible actions.

### Claim-by-Move (Multi-Agent Safety)
First agent to move a file from `/Needs_Action/` to `/In_Progress/{agent}/` owns that task. Prevents duplicate processing.

### Dry-Run Mode
All watchers and executors check `DRY_RUN=true` env var before executing real actions. Always develop with `DRY_RUN=true`.

### Retry Handler Pattern
Exponential backoff: `base_delay × 2^attempt`, capped at 60s. Use `@with_retry(max_attempts=3)` decorator for transient API failures.

## Watcher Scripts

| Script | Trigger | Interval | Output |
|--------|---------|----------|--------|
| `gmail_watcher.py` | Unread/important Gmail | 120s | `EMAIL_{message_id}.md` |
| `whatsapp_watcher.py` | Keywords (urgent, asap, invoice, payment, help) | 30s | `WHATSAPP_{contact}_{date}.md` |
| `filesystem_watcher.py` | Drop-folder file events | Event-driven | `META_{filename}.md` |
| `finance_watcher.py` | Bank CSV/API | Scheduled | `/Accounting/Current_Month.md` |

Base class: `BaseWatcher(ABC)` with `check_for_updates()`, `create_action_file()`, `run()`.

## MCP Configuration

MCP servers are configured in `mcp.json`. Credentials via environment variables only — never hardcoded.

```json
{
  "servers": [
    {
      "name": "email",
      "command": "node",
      "args": ["/path/to/email-mcp/index.js"],
      "env": {"GMAIL_CREDENTIALS": "/path/to/credentials.json"}
    }
  ]
}
```

## Environment Variables

Store in `.env` (already in `.gitignore`). Use OS credential managers for production (Windows Credential Manager, macOS Keychain).

```
GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_CREDENTIALS
BANK_API_TOKEN, BANK_API_URL
WHATSAPP_SESSION_PATH
SLACK_API_KEY
ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PASSWORD
DRY_RUN=true   # Set false only in production
DEV_MODE=true
```

## Delivery Tiers

| Tier | Scope |
|------|-------|
| **Bronze** | Dashboard.md + Handbook + 1 Watcher + basic vault structure |
| **Silver** | 2+ Watchers + LinkedIn posting + HITL workflow + 1 MCP server |
| **Gold** | Full integration + Odoo + social media + CEO Briefing + Ralph loop |
| **Platinum** | Cloud VM + synced vault + work-zone specialization (Cloud drafts, Local approves) |

All AI functionality must be implemented as **Agent Skills** (required at all tiers).

## Audit Logging

All actions logged to `/Logs/YYYY-MM-DD.json`:
```json
{
  "timestamp": "ISO-8601",
  "action_type": "email_send",
  "actor": "claude_code",
  "target": "recipient",
  "approval_status": "approved",
  "approved_by": "human",
  "result": "success"
}
```

## Graceful Degradation Rules

- Gmail API down → queue locally
- Banking API timeout → require fresh approval, no auto-retry
- Claude unavailable → watchers keep collecting
- Vault locked → write to temp, sync when available

## Rate Limits (Enforce in Code)

- Max 10 emails per hour
- Max 3 payments per hour
- WhatsApp: respect Terms of Service (Playwright automation is a gray area)
