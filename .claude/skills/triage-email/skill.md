# Skill: Triage Email

Triage a single email action file from the vault and determine the appropriate response.

## Instructions

You will be given a path to an `EMAIL_*.md` file in `/Needs_Action/` or `/In_Progress/`.

1. **Read** the email file to extract: sender, subject, body.
2. **Read** `Company_Handbook.md` — check if sender is a known contact, check financial thresholds.
3. **Read** `Business_Goals.md` — check current priorities and active projects.
4. **Classify** the email:
   - `routine` — standard business communication, no sensitive content
   - `urgent` — contains: urgent, asap, deadline, overdue, legal, payment
   - `invoice` — client requesting or referencing an invoice
   - `new_contact` — sender not in known contacts
   - `financial` — any dollar amounts, payment requests, contracts

5. **Draft a response** in `/Plans/PLAN_email_<id>.md`:
   ```markdown
   # Email Response Plan — <subject>

   **Original:** <filename>
   **From:** <sender>
   **Classification:** <type>
   **Priority:** high/medium/low

   ## Proposed Response

   <drafted reply text>

   ## Actions Required
   - [ ] Send reply (pending human approval)
   - [ ] Log to CRM / accounting if relevant
   ```

6. **Create approval request** in `/Pending_Approval/EMAIL_reply_<id>.md`:
   ```yaml
   ---
   action_type: email_send
   to: <sender email>
   subject: Re: <original subject>
   body_plan: /Plans/PLAN_email_<id>.md
   original_task: <filename>
   priority: <high/medium/low>
   created: <ISO timestamp>
   status: pending_approval
   ---

   <full draft email body here>
   ```

7. Move original email file to `/In_Progress/claude/`.
8. Output: `<promise>TASK_COMPLETE</promise>`

## Usage

```
/triage-email EMAIL_abc123_20260107.md
```
