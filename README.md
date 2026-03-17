# Personal AI Employee — Bronze Tier

> *Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.*

A Digital FTE (Full-Time Equivalent) powered by Claude Code and Obsidian. The AI proactively manages emails, files, and tasks — asking for human approval before taking any sensitive action.

---

## Architecture

```
Python Watchers          Obsidian Vault (State Machine)       Claude Code
─────────────────        ──────────────────────────────        ────────────
Gmail Watcher    ──→  /Needs_Action  →  /In_Progress
Filesystem       ──→       │                 │              /process-inbox
Watcher                    ↓                 ↓              /triage-email
                    /Pending_Approval    /Plans/            /generate-briefing
                           │
                    Human moves to:
                    /Approved  →  Orchestrator → MCP → Action → /Done
                    /Rejected  →  /Done (archived)
```

**Core loop:** Watcher detects → writes `.md` to vault → Claude reads & plans → human approves → Orchestrator executes.

---

## Quick Start

### 1. Install prerequisites

```bash
# Verify versions
python --version    # 3.13+
node --version      # v24+
claude --version

# Install Python dependencies
uv sync

# Install Playwright browsers (for Silver tier)
uv run playwright install chromium
```

### 2. Set up vault

```bash
# Create your Obsidian vault from the template
python scripts/setup_vault.py --vault ~/AI_Employee_Vault

# Open ~/AI_Employee_Vault in Obsidian
```

### 3. Configure credentials

```bash
cp .env.example .env
# Edit .env — set VAULT_PATH, GMAIL_CREDENTIALS_PATH, etc.
```

### 4. Run watchers

```bash
# Filesystem watcher (no credentials needed — great for testing)
DRY_RUN=true python -m src.watchers.filesystem_watcher

# Gmail watcher (requires credentials.json from Google Cloud Console)
DRY_RUN=true python -m src.watchers.gmail_watcher

# Orchestrator
DRY_RUN=true python -m src.orchestrator
```

### 5. Use Agent Skills in Claude Code

```
# Process all items in /Needs_Action
/process-inbox

# Triage a specific email
/triage-email EMAIL_abc123_20260107.md

# Generate CEO briefing
/generate-briefing
```

### 6. Production (PM2)

```bash
npm install -g pm2
pm2 start src/watchers/gmail_watcher.py --interpreter python3 --name gmail-watcher
pm2 start src/orchestrator.py --interpreter python3 --name orchestrator
pm2 start src/watchdog_monitor.py --interpreter python3 --name watchdog
pm2 save && pm2 startup
```

---

## Vault Structure

| Folder | Purpose |
|--------|---------|
| `/Needs_Action/` | Incoming items from watchers |
| `/In_Progress/` | Claimed by an agent (claim-by-move) |
| `/Plans/` | Claude's step-by-step action plans |
| `/Pending_Approval/` | Actions waiting for human approval |
| `/Approved/` | Human-approved → Orchestrator executes |
| `/Rejected/` | Rejected items (audit trail) |
| `/Done/` | Completed tasks |
| `/Logs/` | JSON audit logs (`YYYY-MM-DD.json`) |
| `/Accounting/` | Transactions and financial summaries |
| `/Briefings/` | Weekly CEO briefings |

---

## Gmail API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download `credentials.json`
5. Set `GMAIL_CREDENTIALS_PATH` in `.env`
6. Run once manually — browser will open for OAuth consent

---

## Running Tests

```bash
uv run pytest tests/ -v
```

---

## Delivery Tiers

| Tier | What's Built |
|------|-------------|
| **Bronze** ✅ | This repo — Dashboard, Handbook, Gmail/Filesystem Watcher, Orchestrator, Agent Skills |
| **Silver** | + WhatsApp watcher, LinkedIn posting, MCP server |
| **Gold** | + Odoo, social media, CEO Briefing, Ralph loop |
| **Platinum** | + Cloud VM, synced vault, work-zone specialization |

---

## Security

- All credentials in `.env` (gitignored) — never in vault or code
- `DRY_RUN=true` by default — no real actions until you opt in
- Financial actions always require human approval regardless of `DRY_RUN`
- Rate limits enforced: 10 emails/hour, 3 payments/hour
- Audit logs retained 90+ days
