#!/usr/bin/env python3
"""
Gmail + Google Tasks utility for Claude.
Uses saved OAuth token (~/Dropbox/AI/gmail-token.json) for all operations.

Gmail usage:
    python3 .../gmail-reply.py reply --thread-id X --message-id Y --to Z --subject S --body B
    python3 .../gmail-reply.py send --to Z --subject S --body B

Attachment usage:
    python3 .../gmail-reply.py attachments-list --message-id X
    python3 .../gmail-reply.py attachments-download --message-id X --attachment-id Y --filename Z [--save-dir /path/to/dir]

Tasks usage:
    python3 .../gmail-reply.py tasks-list                          # list all task lists
    python3 .../gmail-reply.py tasks-show [--tasklist @default]   # show tasks in a list
    python3 .../gmail-reply.py tasks-add --title "Buy milk" [--due 2026-04-25] [--tasklist @default]
    python3 .../gmail-reply.py tasks-done --task-id <id> [--tasklist @default]
    python3 .../gmail-reply.py tasks-delete --task-id <id> [--tasklist @default]

Or import as a module:
    from gmail_reply import reply_to_thread, add_task, list_attachments, download_attachment
"""

import argparse
import base64
import json
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
from pathlib import Path

TOKEN_FILE = Path(__file__).parent / "gmail-token.json"

def get_credentials():
    if not TOKEN_FILE.exists():
        print(f"ERROR: Token file not found at {TOKEN_FILE}")
        print("Run gmail-setup.py first to generate the token.")
        sys.exit(1)

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    data = json.loads(TOKEN_FILE.read_text())
    creds = Credentials(
        token=data["token"],
        refresh_token=data["refresh_token"],
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data["scopes"],
    )
    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save refreshed token
        data["token"] = creds.token
        TOKEN_FILE.write_text(json.dumps(data, indent=2))
    return creds


def reply_to_thread(thread_id: str, message_id: str, to: str, subject: str, body: str) -> dict:
    """Send a reply within an existing Gmail thread."""
    from googleapiclient.discovery import build

    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    # Build reply message
    msg = MIMEText(body)
    msg["To"] = to
    msg["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
    msg["In-Reply-To"] = message_id
    msg["References"] = message_id

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    body_payload = {"raw": raw, "threadId": thread_id}

    result = service.users().messages().send(userId="me", body=body_payload).execute()
    print(f"✅ Reply sent. Message ID: {result['id']}")
    return result


def send_email(to: str, subject: str, body: str) -> dict:
    """Send a new email (not a reply)."""
    from googleapiclient.discovery import build

    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    msg = MIMEText(body)
    msg["To"] = to
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"✅ Email sent. Message ID: {result['id']}")
    return result


# ── Gmail Draft with Attachment ───────────────────────────────────────────────

def create_draft_with_attachment(to: list, subject: str, body: str, attachment_path: str) -> dict:
    """Create a Gmail draft with a file attachment.

    Args:
        to: List of recipient email addresses
        subject: Email subject
        body: Plain text email body
        attachment_path: Full path to the file to attach
    """
    from googleapiclient.discovery import build
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    msg = MIMEMultipart()
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Attach file
    att_path = Path(attachment_path)
    if not att_path.exists():
        print(f"ERROR: File not found: {att_path}")
        sys.exit(1)

    mime_type, _ = mimetypes.guess_type(str(att_path))
    if mime_type:
        main_type, sub_type = mime_type.split("/", 1)
    else:
        main_type, sub_type = "application", "octet-stream"

    with open(att_path, "rb") as f:
        part = MIMEBase(main_type, sub_type)
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=att_path.name)
    msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    draft = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    print(f"✅ Draft created with attachment '{att_path.name}'. Draft ID: {draft['id']}")
    return draft


# ── Gmail Attachments ─────────────────────────────────────────────────────────

def _extract_parts(payload: dict) -> list:
    """Recursively extract all message parts (handles nested multipart)."""
    parts = []
    if "parts" in payload:
        for part in payload["parts"]:
            parts.extend(_extract_parts(part))
    else:
        parts.append(payload)
    return parts


def list_attachments(message_id: str) -> list:
    """List all attachments in a Gmail message. Returns list of dicts with name, size, attachmentId."""
    from googleapiclient.discovery import build
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = msg.get("payload", {})
    parts = _extract_parts(payload)

    attachments = []
    for part in parts:
        filename = part.get("filename", "")
        body = part.get("body", {})
        attachment_id = body.get("attachmentId")
        size = body.get("size", 0)
        if filename and attachment_id:
            attachments.append({
                "filename": filename,
                "attachmentId": attachment_id,
                "size": size,
                "mimeType": part.get("mimeType", ""),
            })

    if not attachments:
        print("No attachments found in this message.")
    else:
        print(f"Found {len(attachments)} attachment(s):")
        for a in attachments:
            size_kb = a["size"] / 1024
            print(f"  📎 {a['filename']}  ({size_kb:.1f} KB)  [{a['mimeType']}]")
            print(f"     attachment-id: {a['attachmentId']}")
    return attachments


def download_attachment(message_id: str, attachment_id: str, filename: str, save_dir: str = ".") -> str:
    """Download a Gmail attachment and save to disk. Returns the saved file path."""
    from googleapiclient.discovery import build
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    att = service.users().messages().attachments().get(
        userId="me", messageId=message_id, id=attachment_id
    ).execute()

    data = att.get("data", "")
    file_data = base64.urlsafe_b64decode(data)

    save_path = Path(save_dir) / filename
    save_path.write_bytes(file_data)
    print(f"✅ Attachment saved: {save_path}  ({len(file_data) / 1024:.1f} KB)")
    return str(save_path)


# ── Google Tasks ──────────────────────────────────────────────────────────────

def list_task_lists() -> list:
    """Return all task lists."""
    from googleapiclient.discovery import build
    creds = get_credentials()
    service = build("tasks", "v1", credentials=creds)
    result = service.tasklists().list().execute()
    items = result.get("items", [])
    for item in items:
        print(f"{item['id']:40s}  {item['title']}")
    return items


def list_tasks(tasklist: str = "@default") -> list:
    """List tasks in a task list."""
    from googleapiclient.discovery import build
    creds = get_credentials()
    service = build("tasks", "v1", credentials=creds)
    result = service.tasks().list(tasklist=tasklist, showCompleted=False).execute()
    items = result.get("items", [])
    if not items:
        print("No tasks found.")
    for item in items:
        due = item.get("due", "")[:10] if item.get("due") else "no due date"
        print(f"{item['id']:30s}  [{due}]  {item['title']}")
    return items


def add_task(title: str, due: str = None, tasklist: str = "@default") -> dict:
    """Add a task. due should be YYYY-MM-DD if provided."""
    from googleapiclient.discovery import build
    creds = get_credentials()
    service = build("tasks", "v1", credentials=creds)
    body = {"title": title}
    if due:
        body["due"] = f"{due}T00:00:00.000Z"
    result = service.tasks().insert(tasklist=tasklist, body=body).execute()
    print(f"✅ Task added: '{result['title']}' (ID: {result['id']})")
    return result


def complete_task(task_id: str, tasklist: str = "@default") -> dict:
    """Mark a task as completed."""
    from googleapiclient.discovery import build
    creds = get_credentials()
    service = build("tasks", "v1", credentials=creds)
    result = service.tasks().patch(
        tasklist=tasklist, task=task_id, body={"status": "completed"}
    ).execute()
    print(f"✅ Task marked complete: '{result['title']}'")
    return result


def delete_task(task_id: str, tasklist: str = "@default") -> None:
    """Delete a task."""
    from googleapiclient.discovery import build
    creds = get_credentials()
    service = build("tasks", "v1", credentials=creds)
    service.tasks().delete(tasklist=tasklist, task=task_id).execute()
    print(f"✅ Task deleted: {task_id}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gmail + Google Tasks utility")
    subparsers = parser.add_subparsers(dest="command")

    # reply subcommand
    reply_parser = subparsers.add_parser("reply", help="Reply to a Gmail thread")
    reply_parser.add_argument("--thread-id", required=True)
    reply_parser.add_argument("--message-id", required=True)
    reply_parser.add_argument("--to", required=True)
    reply_parser.add_argument("--subject", required=True)
    reply_parser.add_argument("--body", required=True)

    # send subcommand
    send_parser = subparsers.add_parser("send", help="Send a new email")
    send_parser.add_argument("--to", required=True)
    send_parser.add_argument("--subject", required=True)
    send_parser.add_argument("--body", required=True)

    # draft-with-attachment subcommand
    draft_att_parser = subparsers.add_parser("draft-with-attachment", help="Create a draft email with a file attachment")
    draft_att_parser.add_argument("--to", required=True, help="Recipient email address(es), comma-separated")
    draft_att_parser.add_argument("--subject", required=True)
    draft_att_parser.add_argument("--body", required=True)
    draft_att_parser.add_argument("--file", required=True, help="Full path to the file to attach")

    # attachments-list subcommand
    att_list_parser = subparsers.add_parser("attachments-list", help="List attachments in a message")
    att_list_parser.add_argument("--message-id", required=True, help="Gmail message ID")

    # attachments-download subcommand
    att_dl_parser = subparsers.add_parser("attachments-download", help="Download an attachment")
    att_dl_parser.add_argument("--message-id", required=True, help="Gmail message ID")
    att_dl_parser.add_argument("--attachment-id", required=True, help="Attachment ID (from attachments-list)")
    att_dl_parser.add_argument("--filename", required=True, help="Filename to save as")
    att_dl_parser.add_argument("--save-dir", default=".", help="Directory to save the file (default: current dir)")

    # tasks-list subcommand
    subparsers.add_parser("tasks-list", help="List all Google Task lists")

    # tasks-show subcommand
    tasks_show_parser = subparsers.add_parser("tasks-show", help="Show tasks in a list")
    tasks_show_parser.add_argument("--tasklist", default="@default")

    # tasks-add subcommand
    tasks_add_parser = subparsers.add_parser("tasks-add", help="Add a task")
    tasks_add_parser.add_argument("--title", required=True)
    tasks_add_parser.add_argument("--due", default=None, help="Due date YYYY-MM-DD")
    tasks_add_parser.add_argument("--tasklist", default="@default")

    # tasks-done subcommand
    tasks_done_parser = subparsers.add_parser("tasks-done", help="Mark a task complete")
    tasks_done_parser.add_argument("--task-id", required=True)
    tasks_done_parser.add_argument("--tasklist", default="@default")

    # tasks-delete subcommand
    tasks_delete_parser = subparsers.add_parser("tasks-delete", help="Delete a task")
    tasks_delete_parser.add_argument("--task-id", required=True)
    tasks_delete_parser.add_argument("--tasklist", default="@default")

    args = parser.parse_args()

    if args.command == "draft-with-attachment":
        recipients = [r.strip() for r in args.to.split(",")]
        create_draft_with_attachment(recipients, args.subject, args.body, args.file)
    elif args.command == "attachments-list":
        list_attachments(args.message_id)
    elif args.command == "attachments-download":
        download_attachment(args.message_id, args.attachment_id, args.filename, args.save_dir)
    elif args.command == "reply":
        reply_to_thread(args.thread_id, args.message_id, args.to, args.subject, args.body)
    elif args.command == "send":
        send_email(args.to, args.subject, args.body)
    elif args.command == "tasks-list":
        list_task_lists()
    elif args.command == "tasks-show":
        list_tasks(args.tasklist)
    elif args.command == "tasks-add":
        add_task(args.title, args.due, args.tasklist)
    elif args.command == "tasks-done":
        complete_task(args.task_id, args.tasklist)
    elif args.command == "tasks-delete":
        delete_task(args.task_id, args.tasklist)
    else:
        parser.print_help()
