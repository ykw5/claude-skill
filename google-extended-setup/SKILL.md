---
name: google-extended-setup
description: >
  Set up and use the EXTENDED Google functions for Claude — Gmail, Google
  Tasks, Google Calendar — i.e. everything the standard Claude Code /
  Claude Cowork connectors cannot do but can be added with Python + a
  Google OAuth token. Gmail: attach files, send, reply in-thread, threaded
  reply WITH attachments, download attachments. Google Tasks: full CRUD
  (list / add / edit / complete / reopen / delete) — there is no standard
  Tasks connector, so this is the whole Tasks capability. Google Calendar:
  handled by the standard Calendar connector (documented for completeness).
  This document is self-contained: every capability is given both as a
  ready-to-run script AND as the underlying Google API logic, so Claude can
  either run the provided scripts or rewrite them from the description.
  Use when setting up Google integration on a new machine, when an OAuth
  token is missing/expired, or when a Gmail/Tasks job needs something the
  built-in connectors lack.
---

# Google Extended Setup for Claude

Extends Claude's Google integration beyond the built-in connectors:
**Gmail** attachments/sending, full **Google Tasks**, and **Google
Calendar** notes.

## How to use this skill — two modes

Every capability below is documented twice: a **ready-made script** in
`scripts/`, and a **Logic** note giving the exact Google API calls.

- **If the `scripts/` folder is present** → just run the scripts (commands
  are given per section).
- **If you only have this SKILL.md** (no `scripts/`) → write the Python
  yourself. Each "Logic" note specifies every API call needed, so each
  script can be reproduced from the description alone.

Either way the OAuth token (§2) must exist first.

---

## 1. The picture — three services, standard vs added

| Service | Standard Claude connector | Connector CANNOT | This skill adds |
|---|---|---|---|
| **Gmail** | Gmail MCP — search, read, draft, labels | attach files, send, download attachments | Python scripts (§3) |
| **Google Tasks** | **none** | — | `google_tasks.py` — the entire capability (§4) |
| **Google Calendar** | Calendar MCP — list/get/create/update/delete events, respond, suggest times | nothing missing | nothing needed (§5) |

Pattern: use the **MCP connector** to *find/read* (thread IDs, event
lists), use the **Python scripts** to *act* where the connector can't.

---

## 2. Authentication — one token for everything

All scripts share **one** OAuth token:

```
~/claude-gmail/gmail-token.json
```

It must carry two scopes — that is all Gmail + Tasks need:

```
https://www.googleapis.com/auth/gmail.modify   # read + send + reply + drafts + labels
https://www.googleapis.com/auth/tasks          # Google Tasks
```

`gmail.modify` alone covers every Gmail operation in this skill (reading
messages/attachments, sending, and creating drafts) — no separate
`readonly` or `compose` scope is required.

**Logic (reused by every script).** Load the token JSON; build
`google.oauth2.credentials.Credentials(token, refresh_token, token_uri,
client_id, client_secret, scopes)`; if `creds.expired` refresh with
`google.auth.transport.requests.Request()` and write the new token back;
then `googleapiclient.discovery.build("gmail"|"tasks", "v1", credentials=creds)`.

How to create the token in the first place → §6.

---

## 3. Gmail

**Standard connector can:** search threads, read messages, create drafts
(incl. threaded reply drafts), manage labels.
**Cannot:** attach files, send, download attachments → the scripts below.

Find `<message_id>` / `<thread_id>` with the Gmail MCP connector
(`search_threads` / `get_thread`) — hex strings like `18c4f2a9b0e1d3a7`.

### Script: `gmail_advanced.py`

```bash
python3 gmail_advanced.py attachments-list     --message-id <id>
python3 gmail_advanced.py attachments-download --message-id <id> \
        --attachment-id <id> --filename "file.pdf" --save-dir ~/Downloads
python3 gmail_advanced.py draft-with-attachment --to "a@x.com,b@y.com" \
        --subject "S" --body "B" --file /path/file.pdf
python3 gmail_advanced.py send-with-attachment  --to "a@x.com" \
        --subject "S" --body "B" --file /path/file.pdf
python3 gmail_advanced.py reply --thread-id <tid> --message-id <mid> \
        --to "a@x.com" --subject "S" --body "B"
python3 gmail_advanced.py send  --to "a@x.com" --subject "S" --body "B"
```

### Script: `gmail_reply_with_attachment.py` — threaded reply WITH attachments

The one combination `gmail_advanced.py` misses (its `reply` takes no
`--file`; its attachment commands are not threaded):

```bash
python3 gmail_reply_with_attachment.py --thread-id <tid> --message-id <mid> \
  --to "a@x.com,b@y.com" --subject "Re: ..." --body "Reply text" \
  --file /path/fig1.pdf --file /path/fig2.pdf      # add --send to send now
```

### Logic (to reimplement Gmail actions in Python)

- **Read / attachments.** `users().messages().get(userId="me", id=<id>,
  format="full")`; walk `payload.parts` recursively; an attachment part has
  a `filename` and `body.attachmentId`. Download with
  `users().messages().attachments().get(userId="me", messageId=<id>,
  id=<attId>)` then `base64.urlsafe_b64decode(result["data"])`.
- **Compose a message.** No file → `MIMEText(body)`. With file(s) →
  `MIMEMultipart()`, attach `MIMEText(body)` plus, per file, a `MIMEBase`
  with `set_payload(bytes)`, `encoders.encode_base64`, header
  `Content-Disposition: attachment; filename=...`. Set `To`, `Subject`.
  For a reply also set `In-Reply-To` and `References` to the message id.
- **Send / draft.** `raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()`.
  Payload `{"raw": raw}`; for a threaded message add `"threadId": <tid>`.
  Send → `users().messages().send(userId="me", body=payload)`. Draft →
  `users().drafts().create(userId="me", body={"message": payload})`.
  Threading is done by the API `threadId` field (the header alone is not
  enough).

---

## 4. Google Tasks

**No standard Tasks connector exists** — `google_tasks.py` is the entire
capability. Full CRUD, including edit/reopen.

### Script: `google_tasks.py`

```bash
python3 google_tasks.py lists                              # all task lists
python3 google_tasks.py show   [--tasklist <id>]           # open tasks
python3 google_tasks.py add    --title "T" [--due 2026-05-25] [--notes "N"]
python3 google_tasks.py edit   --task-id <id> [--title "T"] [--due 2026-05-26] [--notes "N"]
python3 google_tasks.py done   --task-id <id>              # mark complete
python3 google_tasks.py reopen --task-id <id>              # un-complete
python3 google_tasks.py delete --task-id <id>
```

Commands default to the `@default` list; `--tasklist <id>` targets another
(IDs from `lists`).

### Logic (to reimplement Tasks in Python)

Google Tasks API v1, `build("tasks", "v1", credentials=creds)`:

- list task lists → `tasklists().list()` → `items[]` (`id`, `title`)
- show tasks → `tasks().list(tasklist=<id>, showCompleted=False)`
- add → `tasks().insert(tasklist=<id>, body={"title","due","notes"})`
- edit → `tasks().patch(tasklist=<id>, task=<tid>, body={changed fields})`
- complete → `tasks().patch(..., body={"status": "completed"})`
- reopen → `tasks().patch(..., body={"status": "needsAction", "completed": None})`
- delete → `tasks().delete(tasklist=<id>, task=<tid>)`
- `due` is an RFC3339 timestamp; date-only is fine: `2026-05-25T00:00:00.000Z`.

---

## 5. Google Calendar

**No custom tooling — none needed.** The standard Google Calendar MCP
connector is complete: `list_calendars`, `list_events`, `get_event`,
`create_event`, `update_event`, `delete_event`, `respond_to_event`,
`suggest_time`. Calendar work goes entirely through the connector; no
script and no calendar scope on the token.

**Logic (only if a future need exceeds the connector).** Google Calendar
API v3, `build("calendar", "v3", credentials=creds)` with scope
`https://www.googleapis.com/auth/calendar`: `events().list/get/insert/
update/delete(calendarId="primary", ...)`. Not currently installed.

---

## 6. One-time setup (per machine / account)

1. **Google Cloud Console** — create/reuse a project; enable the **Gmail
   API** and **Tasks API**; configure the OAuth consent screen (External,
   add your Gmail as a test user); create an **OAuth client ID** of type
   **Desktop app** and download its `client_secret_*.json`.
2. **Python deps:**
   ```bash
   pip3 install --break-system-packages \
     google-api-python-client google-auth-httplib2 google-auth-oauthlib
   ```
3. **Mint the token:**
   ```bash
   python3 gmail_setup.py --credentials ~/Downloads/client_secret_XXX.json
   ```
   A browser opens; sign in, grant access. The token (with the §2 scopes)
   is saved to `~/claude-gmail/gmail-token.json` and auto-refreshes.

**Logic (to reimplement setup).** `google_auth_oauthlib.flow.
InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)` →
`flow.run_local_server(port=0)` → save `token, refresh_token, token_uri,
client_id, client_secret, scopes` as JSON to `~/claude-gmail/gmail-token.json`.

---

## 7. Files and locations

```
~/claude-gmail/gmail-token.json   THE token (gmail.modify + tasks) — shared by all scripts
scripts/gmail_advanced.py         Gmail attachments / send / reply
scripts/gmail_reply_with_attachment.py   threaded reply + attachments
scripts/google_tasks.py           full Google Tasks CRUD
scripts/gmail_setup.py            one-time OAuth setup
scripts/gmail_switch.py           multi-account manager
scripts/gmail-reply.py            older combined Gmail+Tasks script (kept for reference)
```

Tokens and `client_secret_*.json` are never committed — see `.gitignore`.

---

## 8. Multiple Gmail accounts

`gmail_switch.py` keeps one token per account under
`~/claude-gmail/tokens/<email>.json` and swaps the active one:

```bash
python3 gmail_switch.py whoami | list
python3 gmail_switch.py use   <email>
python3 gmail_switch.py ensure <email>          # switch only if needed
python3 gmail_switch.py setup <email> -c <client_secret.json>
```

---

## 9. Troubleshooting

- **`Token not found`** → run `gmail_setup.py` (§6).
- **`token has no Tasks scope`** → re-run `gmail_setup.py` (it requests
  `gmail.modify` + `tasks`).
- **401 / auth errors** → refresh failed; re-run `gmail_setup.py`.
- **Wrong account** → `gmail_switch.py whoami`, then `use <email>`.
- **Attachment fails** → Gmail caps one message at 25 MB; for larger files
  share via Drive and paste the link in the body.
- **Reply not threaded** → pass the real `threadId`; the API `threadId`
  field threads it, not the `In-Reply-To` header alone.
