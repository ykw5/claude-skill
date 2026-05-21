# claude-skill

Custom skills for Claude (Claude Code / Claude Cowork) — capabilities the
standard Google connectors don't cover, taught to Claude and written up so
they can be reused.

## How these skills are written (read this first)

Each skill is **self-contained and copy-pasteable into Claude**. Every
capability is documented two ways:

1. a **ready-to-run Python script** in the skill's `scripts/` folder, and
2. a **"Logic" note** describing the exact API calls behind it.

So either mode works:

- **Scripts present** → Claude runs the `.py` files directly.
- **No scripts** (e.g. you pasted only the `SKILL.md`) → Claude writes the
  Python itself, following the documented logic — every API call is
  specified, so the scripts can be rebuilt from the description alone.

Paste a `SKILL.md` (or this whole repo) into Claude and it will know how to
proceed in either case.

## Skills

### google-extended-setup

Extended Google functions for Claude:

- **Gmail** — attach files, send, reply in-thread, threaded reply *with*
  attachments, download attachments (the Gmail MCP connector can't do these).
- **Google Tasks** — full CRUD (list / add / edit / complete / reopen /
  delete). There is no standard Tasks connector, so the bundled
  `google_tasks.py` is the entire capability.
- **Google Calendar** — handled fully by the standard Calendar MCP
  connector; documented for completeness, no custom tooling needed.

Includes the Google Cloud / OAuth setup steps, a single unified token, and
all helper scripts. See
[google-extended-setup/SKILL.md](google-extended-setup/SKILL.md).

## Note on secrets

These skills call Google APIs with one OAuth token saved **outside** this
repo at `~/claude-gmail/gmail-token.json`. No tokens or client secrets are
committed — see `.gitignore`. Run the setup script (`gmail_setup.py`) on
each machine to mint your own token.
