# claude-skill

Custom skills for Claude (Claude Code / Claude Cowork).

Each subfolder is one skill: a `SKILL.md` (with YAML frontmatter) plus any
supporting scripts.

## Skills

### gmail-extended-setup

How to set up and use the **extended Gmail functions** for Claude —
attaching files, sending, threaded replies, threaded replies *with*
attachments, downloading attachments, Google Tasks, and multiple Gmail
accounts — i.e. everything that goes beyond the built-in Gmail MCP
connector. Includes the OAuth setup steps and the helper scripts.

See [gmail-extended-setup/SKILL.md](gmail-extended-setup/SKILL.md).

## Note on secrets

These skills call the Gmail API with an OAuth token saved **outside** this
repo (in `~/claude-gmail/` and `~/Dropbox/AI/`). No tokens or client
secrets are committed — see `.gitignore`. Run the setup script
(`gmail_setup.py`) on each machine to mint your own token.
