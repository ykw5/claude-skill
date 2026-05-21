#!/usr/bin/env python3
"""
google_tasks.py — full Google Tasks CRUD for Claude.
====================================================
Google Tasks has NO standard Claude connector, so this script is the entire
Tasks capability. It covers what gmail-reply.py's tasks-* commands do AND
adds the missing pieces: edit (change title / due / notes) and reopen.

Token: ~/Dropbox/AI/gmail-token.json  (must include the
       https://www.googleapis.com/auth/tasks scope — see gmail-setup.py).

Commands
--------
  lists                                  List all task lists (id + title)
  show    [--tasklist ID]                Show open tasks in a list
  add     --title T [--due YYYY-MM-DD] [--notes N] [--tasklist ID]
  edit    --task-id ID [--title T] [--due YYYY-MM-DD] [--notes N] [--tasklist ID]
  done    --task-id ID [--tasklist ID]   Mark a task completed
  reopen  --task-id ID [--tasklist ID]   Reopen a completed task
  delete  --task-id ID [--tasklist ID]   Delete a task

All commands default to the @default task list.

Examples
--------
  python3 google_tasks.py add  --title "Email Kjetil" --due 2026-05-25
  python3 google_tasks.py edit --task-id <id> --title "Email Kjetil + Bo" --due 2026-05-26
  python3 google_tasks.py done --task-id <id>
"""
import argparse
import json
import sys
from pathlib import Path

TOKEN_FILE = Path.home() / "Dropbox" / "AI" / "gmail-token.json"


def get_credentials():
    if not TOKEN_FILE.exists():
        sys.exit(f"ERROR: token not found at {TOKEN_FILE}. Run gmail-setup.py (with the tasks scope).")
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    data = json.loads(TOKEN_FILE.read_text())
    if "tasks" not in " ".join(data.get("scopes", [])):
        sys.exit("ERROR: this token has no Tasks scope. Re-run gmail-setup.py to add "
                 "https://www.googleapis.com/auth/tasks")
    creds = Credentials(
        token=data["token"], refresh_token=data["refresh_token"],
        token_uri=data["token_uri"], client_id=data["client_id"],
        client_secret=data["client_secret"], scopes=data["scopes"],
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        data["token"] = creds.token
        TOKEN_FILE.write_text(json.dumps(data, indent=2))
    return creds


def _svc():
    from googleapiclient.discovery import build
    return build("tasks", "v1", credentials=get_credentials())


def _due(date_str):
    """YYYY-MM-DD -> RFC3339 timestamp Google Tasks expects."""
    return f"{date_str}T00:00:00.000Z"


def cmd_lists(_):
    for it in _svc().tasklists().list().execute().get("items", []):
        print(f"{it['id']:40s}  {it['title']}")


def cmd_show(a):
    items = _svc().tasks().list(tasklist=a.tasklist, showCompleted=False).execute().get("items", [])
    if not items:
        print("No open tasks."); return
    for it in items:
        due = it.get("due", "")[:10] if it.get("due") else "no due date"
        print(f"{it['id']:30s}  [{due}]  {it['title']}")


def cmd_add(a):
    body = {"title": a.title}
    if a.due:   body["due"] = _due(a.due)
    if a.notes: body["notes"] = a.notes
    r = _svc().tasks().insert(tasklist=a.tasklist, body=body).execute()
    print(f"Added: '{r['title']}'  (ID: {r['id']})")


def cmd_edit(a):
    body = {}
    if a.title is not None: body["title"] = a.title
    if a.due   is not None: body["due"]   = _due(a.due)
    if a.notes is not None: body["notes"] = a.notes
    if not body:
        sys.exit("Nothing to edit — pass at least one of --title / --due / --notes.")
    r = _svc().tasks().patch(tasklist=a.tasklist, task=a.task_id, body=body).execute()
    print(f"Edited: '{r['title']}'  (ID: {r['id']})")


def cmd_done(a):
    r = _svc().tasks().patch(tasklist=a.tasklist, task=a.task_id,
                             body={"status": "completed"}).execute()
    print(f"Completed: '{r['title']}'")


def cmd_reopen(a):
    # Reopening: clear status back to needsAction and drop the completed timestamp.
    r = _svc().tasks().patch(tasklist=a.tasklist, task=a.task_id,
                             body={"status": "needsAction", "completed": None}).execute()
    print(f"Reopened: '{r['title']}'")


def cmd_delete(a):
    _svc().tasks().delete(tasklist=a.tasklist, task=a.task_id).execute()
    print(f"Deleted task {a.task_id}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Full Google Tasks CRUD for Claude")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("lists", help="List all task lists")

    p = sub.add_parser("show", help="Show open tasks");      p.add_argument("--tasklist", default="@default")

    p = sub.add_parser("add", help="Add a task")
    p.add_argument("--title", required=True)
    p.add_argument("--due", help="YYYY-MM-DD")
    p.add_argument("--notes")
    p.add_argument("--tasklist", default="@default")

    p = sub.add_parser("edit", help="Edit a task's title / due / notes")
    p.add_argument("--task-id", required=True, dest="task_id")
    p.add_argument("--title")
    p.add_argument("--due", help="YYYY-MM-DD")
    p.add_argument("--notes")
    p.add_argument("--tasklist", default="@default")

    for name, helptext in [("done", "Mark a task complete"),
                           ("reopen", "Reopen a completed task"),
                           ("delete", "Delete a task")]:
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--task-id", required=True, dest="task_id")
        p.add_argument("--tasklist", default="@default")

    args = ap.parse_args()
    {"lists": cmd_lists, "show": cmd_show, "add": cmd_add, "edit": cmd_edit,
     "done": cmd_done, "reopen": cmd_reopen, "delete": cmd_delete}[args.command](args)
