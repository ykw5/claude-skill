#!/usr/bin/env python3
"""
gmail_switch.py — manage multiple Gmail accounts for the gmail-attachments skill.

Storage layout
--------------
  ~/claude-gmail/gmail-token.json          # active token (used by gmail_advanced.py)
  ~/claude-gmail/tokens/<email>.json       # one saved token per account

Commands
--------
  whoami                     Print the email address of the active token
  list                       List all saved accounts (* marks the active one)
  save                       Save the active token into tokens/<its-email>.json
  use <email-or-substring>   Activate a saved account (auto-archives current first)
  setup <email> -c <path>    Run OAuth flow, save under <email>, then activate
  ensure <email>             If active != <email>, switch; otherwise no-op (for scripts)

Usage from Claude
-----------------
  Before any gmail_advanced.py call, run:
      python3 ~/claude-gmail/gmail_switch.py ensure <email>
  This guarantees the right account is active without needing to think about it.
"""

import argparse
import json
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DIR = Path.home() / "claude-gmail"
ACTIVE = DIR / "gmail-token.json"
TOKENS = DIR / "tokens"


def _load(path: Path):
    return json.loads(path.read_text())


def _email_of(token_path: Path) -> str:
    """Look up the Gmail address that a saved token belongs to."""
    t = _load(token_path)
    data = urllib.parse.urlencode({
        "client_id": t["client_id"],
        "client_secret": t["client_secret"],
        "refresh_token": t["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(t["token_uri"], data=data)) as r:
        access = json.load(r)["access_token"]
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {access}"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)["emailAddress"]


def _resolve(name: str) -> Path:
    """Resolve a name (full email or substring) to a saved token path."""
    TOKENS.mkdir(parents=True, exist_ok=True)
    candidates = sorted(TOKENS.glob("*.json"))
    if not candidates:
        sys.exit("No saved accounts. Run 'setup' or 'save' first.")
    # exact filename match
    exact = TOKENS / f"{name}.json"
    if exact in candidates:
        return exact
    # substring match
    matches = [p for p in candidates if name.lower() in p.stem.lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        sys.exit(f"No saved account matches '{name}'. Try: list")
    sys.exit("Ambiguous: " + ", ".join(p.stem for p in matches))


def cmd_whoami(_):
    if not ACTIVE.exists():
        sys.exit("No active token at " + str(ACTIVE))
    print(_email_of(ACTIVE))


def cmd_list(_):
    TOKENS.mkdir(parents=True, exist_ok=True)
    active_email = _email_of(ACTIVE) if ACTIVE.exists() else None
    found = sorted(TOKENS.glob("*.json"))
    if not found:
        print("(no saved accounts yet — run 'save' or 'setup')")
        if active_email:
            print(f"active: {active_email} (not yet saved)")
        return
    for p in found:
        marker = "*" if p.stem == active_email else " "
        print(f"{marker} {p.stem}")
    if active_email and not (TOKENS / f"{active_email}.json").exists():
        print(f"  (active token {active_email} is not yet saved — run 'save')")


def cmd_save(_):
    if not ACTIVE.exists():
        sys.exit("No active token to save.")
    TOKENS.mkdir(parents=True, exist_ok=True)
    email = _email_of(ACTIVE)
    dest = TOKENS / f"{email}.json"
    shutil.copy2(ACTIVE, dest)
    print(f"Saved active token as {dest}")


def cmd_use(args):
    target = _resolve(args.name)
    # archive current first so we never lose it
    if ACTIVE.exists():
        try:
            current_email = _email_of(ACTIVE)
            backup = TOKENS / f"{current_email}.json"
            if not backup.exists() or backup.read_bytes() != ACTIVE.read_bytes():
                shutil.copy2(ACTIVE, backup)
        except Exception as e:
            print(f"warning: could not archive current token: {e}", file=sys.stderr)
    shutil.copy2(target, ACTIVE)
    print(f"Active account is now: {_email_of(ACTIVE)}")


def cmd_ensure(args):
    """No-op if already active; otherwise switch. Designed to be called from scripts."""
    target_path = _resolve(args.email)
    target_email = target_path.stem
    if ACTIVE.exists():
        try:
            if _email_of(ACTIVE) == target_email:
                print(f"already active: {target_email}")
                return
        except Exception:
            pass
    cmd_use(args.__class__(name=args.email)) if False else cmd_use(argparse.Namespace(name=args.email))


def cmd_setup(args):
    setup_script = DIR / "gmail_setup.py"
    if not setup_script.exists():
        sys.exit(f"Missing {setup_script}")
    creds = Path(args.credentials).expanduser()
    if not creds.exists():
        sys.exit(f"Credentials not found: {creds}")
    print(f"Running OAuth flow for {args.email} — sign in with that account in the browser...")
    subprocess.check_call([sys.executable, str(setup_script), "--credentials", str(creds)])
    # after setup, ACTIVE has been overwritten — verify and rename
    actual = _email_of(ACTIVE)
    if actual.lower() != args.email.lower():
        print(f"warning: signed in as {actual}, not {args.email}", file=sys.stderr)
    TOKENS.mkdir(parents=True, exist_ok=True)
    dest = TOKENS / f"{actual}.json"
    shutil.copy2(ACTIVE, dest)
    print(f"Saved as {dest} and set as active.")


def main():
    p = argparse.ArgumentParser(description="Switch between saved Gmail accounts.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami").set_defaults(func=cmd_whoami)
    sub.add_parser("list").set_defaults(func=cmd_list)
    sub.add_parser("save").set_defaults(func=cmd_save)

    u = sub.add_parser("use")
    u.add_argument("name")
    u.set_defaults(func=cmd_use)

    e = sub.add_parser("ensure")
    e.add_argument("email")
    e.set_defaults(func=cmd_ensure)

    s = sub.add_parser("setup")
    s.add_argument("email")
    s.add_argument("-c", "--credentials", required=True)
    s.set_defaults(func=cmd_setup)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
