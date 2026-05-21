# claude-skill

Custom skills for Claude (Claude Code / Claude Cowork).

Each subfolder is one skill: a `SKILL.md` (with YAML frontmatter) plus any
supporting scripts.

## Skills

### google-extended-setup

How to set up and use the **extended Google functions** for Claude:

- **Gmail** — attach files, send, reply in-thread, threaded reply *with*
  attachments, download attachments (the Gmail MCP connector can't do these).
- **Google Tasks** — full CRUD (list / add / edit / complete / reopen /
  delete). There is no standard Tasks connector, so the bundled
  `google_tasks.py` is the entire capability.
- **Google Calendar** — handled fully by the standard Calendar MCP
  connector; documented for completeness, no custom tooling needed.

Includes the Google Cloud / OAuth setup steps and all helper scripts.

See [google-extended-setup/SKILL.md](google-extended-setup/SKILL.md).

## Note on secrets

These skills call Google APIs with OAuth tokens saved **outside** this repo
(in `~/claude-gmail/` and `~/Dropbox/AI/`). No tokens or client secrets are
committed — see `.gitignore`. Run the setup script (`gmail_setup.py`) on
each machine to mint your own token.
