---
name: google-extended-setup
description: >
  How to set up and use the EXTENDED Google functions for Claude — Gmail,
  Google Tasks, and Google Calendar — i.e. everything the standard Claude
  Code / Claude Cowork connectors cannot do but has been wired up with
  Python + OAuth. Gmail: attach files, send, reply in-thread, threaded
  reply WITH attachments, download attachments. Google Tasks: full CRUD
  (list / add / edit / complete / reopen / delete) — there is no standard
  Tasks connector, so this script IS the whole Tasks capability. Google
  Calendar: handled fully by the standard Calendar connector (documented
  here for completeness). Use this skill when setting up Google
  integration on a new machine, when an OAuth token is missing or expired,
  when troubleshooting Google authentication, or whenever a Gmail / Tasks
  job needs a capability the built-in connectors lack.
---

# Google Extended Setup for Claude

How Gmail, Google Tasks, and Google Calendar are wired into Claude — what
the standard connectors do, what extra Python tooling fills the gaps, how to
set it all up, and the exact commands.

---

## 1. The picture — three services, standard vs added

| Service | Standard Claude connector | Connector CANNOT | Extension (this skill) |
|---|---|---|---|
| **Gmail** | Gmail MCP — search, read, draft (incl. threaded reply drafts), labels | attach files, send, download attachments | Python scripts (§2) |
| **Google Tasks** | **none** | — | `google_tasks.py` — the *entire* Tasks capability (§3) |
| **Google Calendar** | Calendar MCP — list/get/create/update/delete events, respond to invites, suggest times | (complete — nothing missing) | none needed (§4) |

Pattern: use the **MCP connector** to *find/read* (thread IDs, event lists),
use the **Python scripts** to *act* where the connector can't.

---

## 2. Gmail

**Standard connector can:** search threads, read full messages, create drafts
(including threaded reply drafts via `replyToMessageId`), manage labels.

**Standard connector cannot:** attach a file, send, download attachments.

**The Python extension covers all of that.** Script: `gmail_advanced.py`
(token `~/claude-gmail/gmail-token.json`).

```bash
# List / download attachments from a received email
python3 gmail_advanced.py attachments-list     --message-id <id>
python3 gmail_advanced.py attachments-download --message-id <id> \
        --attachment-id <id> --filename "file.pdf" --save-dir ~/Downloads

# New email with an attachment (draft, or send)
python3 gmail_advanced.py draft-with-attachment --to "a@x.com,b@y.com" \
        --subject "S" --body "B" --file /path/file.pdf
python3 gmail_advanced.py send-with-attachment  --to "a@x.com" \
        --subject "S" --body "B" --file /path/file.pdf

# Threaded reply (plain text) / plain new email
python3 gmail_advanced.py reply --thread-id <tid> --message-id <mid> \
        --to "a@x.com" --subject "S" --body "B"
python3 gmail_advanced.py send  --to "a@x.com" --subject "S" --body "B"
```

Find `<message_id>` / `<thread_id>` with the Gmail MCP connector
(`search_threads` / `get_thread`) — hex strings like `18c4f2a9b0e1d3a7`.
Always offer **draft** before **send**.

### The one Gmail gap — threaded reply WITH attachments

`gmail_advanced.py` does threaded reply OR attachment, not both at once.
`gmail_reply_with_attachment.py` (bundled here) closes it — a threaded
reply, draft or send, with one or more attachments:

```bash
python3 gmail_reply_with_attachment.py \
  --thread-id <tid> --message-id <mid> \
  --to "a@x.com,b@y.com" --subject "Re: ..." --body "Reply text" \
  --file /path/fig1.pdf --file /path/fig2.pdf      # add --send to send now
```

---

## 3. Google Tasks

**There is no standard Tasks connector for Claude.** `google_tasks.py`
(bundled here) is the entire capability — full CRUD, including edit/reopen
that the older `gmail-reply.py tasks-*` commands lacked.

Token: `~/Dropbox/AI/gmail-token.json` — must carry the
`https://www.googleapis.com/auth/tasks` scope.

```bash
python3 google_tasks.py lists                              # all task lists
python3 google_tasks.py show   [--tasklist <id>]           # open tasks
python3 google_tasks.py add    --title "T" [--due 2026-05-25] [--notes "N"]
python3 google_tasks.py edit   --task-id <id> [--title "T"] [--due 2026-05-26] [--notes "N"]
python3 google_tasks.py done   --task-id <id>              # mark complete
python3 google_tasks.py reopen --task-id <id>              # un-complete
python3 google_tasks.py delete --task-id <id>
```

All commands default to the `@default` task list; pass `--tasklist <id>`
(get IDs from `lists`) for another. `edit` is a `patch` — pass only the
fields you want changed.

(The older `gmail-reply.py` also has `tasks-add/show/list/done/delete` —
a subset, no edit/reopen. Prefer `google_tasks.py`.)

---

## 4. Google Calendar

**No custom tooling — and none is needed.** The standard Google Calendar
MCP connector is complete. It can:

- `list_calendars` — all calendars
- `list_events` / `get_event` — read events
- `create_event` — add an event
- `update_event` — change an event
- `delete_event` — remove an event
- `respond_to_event` — accept / decline / tentative an invite
- `suggest_time` — propose meeting slots

So Calendar work goes entirely through the connector. There is no Calendar
Python script and no token carries a calendar scope. If a future need
exceeds the connector, that is when a `google_calendar.py` would be added
here — at present there is nothing extra to install.

---

## 5. One-time setup (per machine / account)

### 5.1 Google Cloud Console
1. Create or reuse a Google Cloud project.
2. Enable the **Gmail API** and the **Tasks API**.
3. Configure the OAuth consent screen (External; add your Gmail as a test
   user — no app verification needed for personal use).
4. Create an **OAuth client ID**, type **Desktop app**; download its
   `client_secret_*.json`.

### 5.2 Python dependencies
```bash
pip3 install --break-system-packages \
  google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 5.3 Mint the token
```bash
python3 gmail_setup.py --credentials ~/Downloads/client_secret_XXX.json
```
A browser opens; sign in and grant access. The refresh token is saved and
auto-refreshes thereafter. Run once per account.

### 5.4 Scopes — aim for ONE token that does everything
For a clean install request all of these in setup so a single token powers
Gmail **and** Tasks:
```
https://www.googleapis.com/auth/gmail.modify     (read + send + reply + label)
https://www.googleapis.com/auth/gmail.compose    (drafts)
https://www.googleapis.com/auth/tasks            (Google Tasks)
```
(Calendar needs no token here — it uses the MCP connector.)

---

## 6. Files and locations

```
~/claude-gmail/gmail-token.json     OAuth token — scopes: gmail.modify,
                                    gmail.compose, gmail.readonly
~/claude-gmail/gmail_advanced.py    Gmail attachments / send / reply
~/claude-gmail/gmail_setup.py       One-time OAuth setup
~/claude-gmail/gmail_switch.py      Multi-account manager
~/claude-gmail/tokens/<email>.json  One saved token per account

~/Dropbox/AI/gmail-token.json       OAuth token — scopes: gmail.modify, tasks
~/Dropbox/AI/gmail-reply.py         Gmail + a Tasks subset (older)
```

The user currently has **two tokens** (Gmail-attachment scripts use the
`~/claude-gmail` one; Tasks uses the `~/Dropbox/AI` one). A future cleanup
is to mint one token with all of §5.4's scopes and point everything at it.

All scripts referenced above are bundled in this skill's `scripts/` folder
so the setup can be reproduced on a new machine.

---

## 7. Multiple Gmail accounts

`gmail_advanced.py` uses one token at a time. `gmail_switch.py` keeps one
token per account under `~/claude-gmail/tokens/<email>.json`:

```bash
python3 gmail_switch.py whoami | list
python3 gmail_switch.py use   <email>            # activate
python3 gmail_switch.py ensure <email>           # switch only if needed
python3 gmail_switch.py setup <email> -c <client_secret.json>
```

---

## 8. Account routing convention

A sensible division of labour:

- Gmail read / search / draft text → Gmail MCP connector
- Gmail send / reply / attachments → the Python scripts (§2)
- Google Tasks (any operation)     → `google_tasks.py` (§3)
- Google Calendar (any operation)  → the Calendar MCP connector (§4)
- Secondary Gmail accounts with no saved token → a browser tool instead

---

## 9. Troubleshooting

- **`Token not found`** → run `gmail_setup.py` (§5.3).
- **`token has no Tasks scope`** → re-run `gmail_setup.py` requesting the
  `tasks` scope (§5.4).
- **401 / auth errors** → the refresh failed; re-run `gmail_setup.py`.
- **Wrong account** → `gmail_switch.py whoami`, then `use <email>`.
- **Attachment fails** → Gmail caps one message at 25 MB; for bigger files
  share via Drive and paste the link.
- **Reply not threaded** → pass the real `threadId`; the API `threadId`
  field is what threads it, not the `In-Reply-To` header alone.
