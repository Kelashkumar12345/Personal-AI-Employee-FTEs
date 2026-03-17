# Skill: Process Inbox

Process all items in the vault's /Needs_Action folder according to the Company Handbook and Business Goals.

## Instructions

You are acting as the AI Employee. Execute the following steps for EACH file in `/Needs_Action/`:

1. **Read** the task file (frontmatter + body).
2. **Read** `Company_Handbook.md` to understand the rules of engagement.
3. **Read** `Business_Goals.md` to understand current priorities.
4. **Classify** the item: EMAIL | DOCUMENT | WHATSAPP | FILE | DATA | NOTE
5. **Decide**: Can this be handled automatically, or does it need human approval?

### Auto-handle (no approval needed):
- Logging and filing documents
- Generating draft plans in `/Plans/`
- Updating `Dashboard.md`
- Creating summaries or briefings

### Requires approval (create file in `/Pending_Approval/`):
- Sending any message or email
- Financial actions
- Any action with external impact

6. **Act**:
   - If auto-handle: perform the action, then move the task file to `/Done/`.
   - If approval needed: create an approval request file in `/Pending_Approval/` with this frontmatter:
     ```yaml
     ---
     action_type: <email_send|payment|post_social|...>
     to: <recipient>
     subject: <subject if applicable>
     amount: <amount if financial>
     reason: <why this action is needed>
     original_task: <filename from Needs_Action>
     created: <ISO timestamp>
     status: pending_approval
     ---
     ```
   Then move the original task to `/In_Progress/claude/`.

7. **Log** every action to `/Logs/YYYY-MM-DD.json`.

8. When ALL items are processed, output: `<promise>TASK_COMPLETE</promise>`

## Usage

```
/process-inbox
```

Or with vault path override:
```
/process-inbox VAULT_PATH=/path/to/vault
