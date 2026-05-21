---
name: gmail-extended-setup
description: >
  How to set up and use the EXTENDED Gmail functions for Claude — the
  capabilities that go beyond the basic Gmail MCP connector built into
  Claude Code / Claude Cowork: attaching files, sending email, threaded
  replies, threaded replies WITH attachments, downloading attachments,
  Google Tasks, and multiple Gmail accounts. Use this skill when setting
  up Gmail integration on a new machine, when the Gmail token is missing
  or expired, when troubleshooting Gmail authentication, or whenever a
  Gmail task needs a capability the built-in connector does not have
  (attach a file, send, reply-with-file). It documents both the
  architecture and the exact commands.
---

# Gmail Extended Setup for Claude

How the user's Gmail integration is layered, what each layer can do, how to
set it up from scratch, and the exact commands.

---

## 1. The two layers

**Layer 1 — the basic Gmail MCP connector.** Built into Claude Code / Claude
Cowork via a Google OAuth connection (the "Gmail" connector you enable in the
client). It is convenient but limited:

| Layer 1 CAN | Layer 1 CANNOT |
|---|---|
| search threads / messages | attach a file to an email |
| read full thread + message bodies | send an email |
| create drafts (incl. threaded reply drafts) | download an attachment from an email |
| manage labels | Google Tasks |

**Layer 2 — Python extension scripts (this skill).** A few small Python
scripts that call the Gmail API directly with a saved OAuth token. They cover
everything Layer 1 cannot: attachments, sending, threaded replies, Tasks,
multi-account. Layer 2 is what makes Gmail "fully work" with Claude.

The two layers are used together: use the **MCP connector** to *find* thread
and message IDs (search/read), then use the **Python scripts** to *act*
(attach / send / reply).

---

## 2. The additional functions (what Layer 2 adds)

1. **List attachments** in any received email.
2. **Download attachments** to local disk.
3. **Create a draft with file attachment(s)**.
4. **Send an email with file attachment(s)**.
5. **Reply within a thread** (plain text — keeps the conversation threaded).
6. **Reply within a thread WITH attachments** (draft or send) — see §6;
   this is the one combination the stock scripts miss.
7. **Send a plain new email**.
8. **Google Tasks** — list / add / complete / delete tasks.
9. **Multiple Gmail accounts** — save several tokens and switch between them.

---

## 3. One-time setup (do this once per machine / account)

### 3.1 Google Cloud Console

1. Create (or reuse) a Google Cloud project.
2. Enable the **Gmail API** (and the **Tasks API** if you want Google Tasks).
3. Configure the OAuth consent screen (External; add your Gmail as a test
   user is enough — no verification needed for personal use).
4. Create an **OAuth client ID** of type **Desktop app**. Download its
   `client_secret_*.json`.

### 3.2 Python dependencies

```bash
pip3 install --break-system-packages \
  google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 3.3 Run the OAuth flow → save a token

```bash
python3 scripts/gmail_setup.py --credentials ~/Downloads/client_secret_XXX.json
```

A browser opens; sign in with the target Gmail account and grant access.
The refresh token is saved to **`~/claude-gmail/gmail-token.json`** and
auto-refreshes thereafter. You only run this once.

Scopes requested: `gmail.modify`, `gmail.compose`, `gmail.readonly`
(the Dropbox/AI variant — see §7 — also requests `tasks`).

### 3.4 Verify

```bash
python3 scripts/gmail_advanced.py attachments-list --message-id <any_id>
```

If it prints without an auth error, Layer 2 is live.

---

## 4. Files and locations

```
~/claude-gmail/gmail-token.json     Active OAuth token (auto-refreshing)
~/claude-gmail/gmail_advanced.py    Main extension script (attach/send/reply)
~/claude-gmail/gmail_setup.py       One-time OAuth setup
~/claude-gmail/gmail_switch.py      Multi-account manager
~/claude-gmail/tokens/<email>.json  One saved token per account

~/Dropbox/AI/gmail-reply.py         Alternative script — same Gmail funcs
                                    PLUS Google Tasks (see §7)
~/Dropbox/AI/gmail-token.json       Token for the Dropbox/AI script
```

Copies of all of these scripts are bundled in this skill's `scripts/`
folder so the setup can be reproduced on a new machine.

---

## 5. Commands — `gmail_advanced.py`

Find `<message_id>` / `<thread_id>` first with the MCP connector
(`search_threads` / `get_thread`). They are hex strings, e.g. `18c4f2a9b0e1d3a7`.

```bash
# List attachments in a message
python3 ~/claude-gmail/gmail_advanced.py attachments-list --message-id <id>

# Download an attachment
python3 ~/claude-gmail/gmail_advanced.py attachments-download \
  --message-id <id> --attachment-id <id> --filename "file.pdf" --save-dir ~/Downloads

# Draft a NEW email with an attachment (not threaded)
python3 ~/claude-gmail/gmail_advanced.py draft-with-attachment \
  --to "a@x.com,b@y.com" --subject "S" --body "B" --file /path/file.pdf

# Send a NEW email with an attachment
python3 ~/claude-gmail/gmail_advanced.py send-with-attachment \
  --to "a@x.com" --subject "S" --body "B" --file /path/file.pdf

# Reply inside an existing thread (plain text, no attachment)
python3 ~/claude-gmail/gmail_advanced.py reply \
  --thread-id <tid> --message-id <mid> --to "a@x.com" --subject "S" --body "B"

# Send a plain new email
python3 ~/claude-gmail/gmail_advanced.py send --to "a@x.com" --subject "S" --body "B"
```

Always offer **draft** before **send** unless the user says to send now.

---

## 6. The gap: threaded reply WITH attachments

`gmail_advanced.py` can do *threaded reply* OR *attachment*, but **not both
in one call** — `reply` takes no `--file`, and `draft-with-attachment` /
`send-with-attachment` are not threaded. (Internally its `_build_message`
helper *does* support attachment + `threadId` + `In-Reply-To` together; only
the CLI subcommands don't wire all three.)

This skill bundles **`scripts/gmail_reply_with_attachment.py`** to close the
gap. It does a threaded reply, draft or send, with one or more attachments:

```bash
# Draft a threaded reply with two attachments (default = draft)
python3 scripts/gmail_reply_with_attachment.py \
  --thread-id <thread_id> --message-id <message_id> \
  --to "a@x.com,b@y.com" --subject "Re: ..." --body "Reply text" \
  --file /path/fig1.pdf --file /path/fig2.pdf

# Same, but send immediately
python3 scripts/gmail_reply_with_attachment.py ... --send
```

It reuses the `~/claude-gmail/gmail-token.json` token and threads the message
via the Gmail API `threadId` field (the reliable mechanism) plus
`In-Reply-To` / `References` headers.

Note: the MCP connector's `create_draft` accepts a `replyToMessageId` (good
for threaded *text* drafts) but its own docs say attachments on drafts are
not supported — so for "threaded reply + attachment" always use this script.

---

## 7. Google Tasks — `gmail-reply.py` (Dropbox/AI variant)

`~/Dropbox/AI/gmail-reply.py` is a parallel script with the same Gmail
functions plus **Google Tasks** (its token at `~/Dropbox/AI/gmail-token.json`
carries the `tasks` scope). Use it for task operations:

```bash
python3 ~/Dropbox/AI/gmail-reply.py tasks-add  --title "Buy milk" [--due 2026-04-25]
python3 ~/Dropbox/AI/gmail-reply.py tasks-show
python3 ~/Dropbox/AI/gmail-reply.py tasks-list                 # list all task lists
python3 ~/Dropbox/AI/gmail-reply.py tasks-done   --task-id <id>
python3 ~/Dropbox/AI/gmail-reply.py tasks-delete --task-id <id>
```

All task commands default to the `@default` list; add `--tasklist <id>` for
another list. This variant also has `reply`, `send`, `draft-with-attachment`,
`attachments-list`, `attachments-download`.

---

## 8. Multiple Gmail accounts — `gmail_switch.py`

`gmail_advanced.py` uses one token at a time. `gmail_switch.py` stores one
token per account under `~/claude-gmail/tokens/<email>.json` and swaps the
active one:

```bash
python3 ~/claude-gmail/gmail_switch.py whoami            # active account
python3 ~/claude-gmail/gmail_switch.py list              # all saved (* = active)
python3 ~/claude-gmail/gmail_switch.py use <email>       # activate one
python3 ~/claude-gmail/gmail_switch.py setup <email> -c <client_secret.json>
python3 ~/claude-gmail/gmail_switch.py ensure <email>    # switch only if needed
```

Before a script call that must hit a specific account, run
`gmail_switch.py ensure <email>` first.

---

## 9. Account routing convention

A sensible division of labour between the two layers:

- Read / search / draft (text)  → Gmail MCP connector
- Send / reply / attachments    → the Python scripts in this skill
- Google Tasks                  → `gmail-reply.py tasks-*`
- Secondary Gmail accounts that have no saved token → operate them through
  a browser tool (e.g. a Claude browser extension) instead.

---

## 10. Troubleshooting

- **`Token not found`** → run `gmail_setup.py` (§3.3).
- **Auth / 401 errors** → the token's refresh failed; re-run `gmail_setup.py`
  to mint a fresh token.
- **Wrong account** → `gmail_switch.py whoami`, then `use <email>`.
- **Attachment fails** → Gmail caps a single message at 25 MB; for bigger
  files put them on Drive and paste the link in the body.
- **Reply not threaded** → make sure you passed the real `threadId`; the
  `In-Reply-To` header alone is not enough — the API `threadId` field is.
- **`google-auth-oauthlib` missing** → install the three packages in §3.2.
