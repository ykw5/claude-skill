#!/usr/bin/env python3
"""
Gmail Advanced Utility for Claude.
Handles attachments, drafts with files, replies, and sending.

Token location: ~/claude-gmail/gmail-token.json
Setup:  python3 ~/claude-gmail/gmail_setup.py

Commands:
  attachments-list        --message-id <id>
  attachments-download    --message-id <id> --attachment-id <id> --filename <name> [--save-dir ~/Downloads]
  draft-with-attachment   --to <email> --subject <s> --body <b> --file <path>
  send-with-attachment    --to <email> --subject <s> --body <b> --file <path>
  reply                   --thread-id <id> --message-id <id> --to <email> --subject <s> --body <b>
  send                    --to <email> --subject <s> --body <b>
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

TOKEN_FILE = Path.home() / "claude-gmail" / "gmail-token.json"


def get_credentials():
    if not TOKEN_FILE.exists():
        print(f"ERROR: Token not found at {TOKEN_FILE}")
        print("Run:  python3 ~/claude-gmail/gmail_setup.py")
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
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        data["token"] = creds.token
        TOKEN_FILE.write_text(json.dumps(data, indent=2))
    return creds


# ── Attachments ───────────────────────────────────────────────────────────────

def _extract_parts(payload: dict) -> list:
    parts = []
    if "parts" in payload:
        for part in payload["parts"]:
            parts.extend(_extract_parts(part))
    else:
        parts.append(payload)
    return parts


def list_attachments(message_id: str) -> list:
    """List all attachments in a Gmail message."""
    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=get_credentials())
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    parts = _extract_parts(msg.get("payload", {}))

    attachments = []
    for part in parts:
        filename = part.get("filename", "")
        body = part.get("body", {})
        att_id = body.get("attachmentId")
        if filename and att_id:
            attachments.append({
                "filename": filename,
                "attachmentId": att_id,
                "size": body.get("size", 0),
                "mimeType": part.get("mimeType", ""),
            })

    if not attachments:
        print("No attachments found.")
    else:
        print(f"Found {len(attachments)} attachment(s):")
        for a in attachments:
            print(f"  📎 {a['filename']}  ({a['size']/1024:.1f} KB)  [{a['mimeType']}]")
            print(f"     attachment-id: {a['attachmentId']}")
    return attachments


def download_attachment(message_id: str, attachment_id: str, filename: str, save_dir: str = ".") -> str:
    """Download a Gmail attachment to disk."""
    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=get_credentials())
    att = service.users().messages().attachments().get(
        userId="me", messageId=message_id, id=attachment_id
    ).execute()
    file_data = base64.urlsafe_b64decode(att.get("data", ""))
    save_path = Path(save_dir).expanduser() / filename
    save_path.write_bytes(file_data)
    print(f"✅ Saved: {save_path}  ({len(file_data)/1024:.1f} KB)")
    return str(save_path)


# ── Build MIME message with optional attachment ────────────────────────────────

def _build_message(to: list, subject: str, body: str, file_path: str = None,
                   thread_id: str = None, message_id: str = None) -> dict:
    if file_path:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body, "plain"))
        att_path = Path(file_path).expanduser()
        if not att_path.exists():
            print(f"ERROR: File not found: {att_path}")
            sys.exit(1)
        mime_type, _ = mimetypes.guess_type(str(att_path))
        main_type, sub_type = (mime_type.split("/", 1) if mime_type else ("application", "octet-stream"))
        with open(att_path, "rb") as f:
            part = MIMEBase(main_type, sub_type)
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=att_path.name)
        msg.attach(part)
    else:
        msg = MIMEText(body, "plain")

    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if message_id:
        msg["In-Reply-To"] = message_id
        msg["References"] = message_id

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id
    return payload


# ── Email operations ──────────────────────────────────────────────────────────

def create_draft(to: list, subject: str, body: str, file_path: str = None) -> dict:
    """Create a Gmail draft, optionally with an attachment."""
    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=get_credentials())
    payload = _build_message(to, subject, body, file_path)
    draft = service.users().drafts().create(
        userId="me", body={"message": payload}
    ).execute()
    label = f" + {Path(file_path).name}" if file_path else ""
    print(f"✅ Draft created{label}. Draft ID: {draft['id']}")
    return draft


def send_email(to: list, subject: str, body: str, file_path: str = None) -> dict:
    """Send an email, optionally with an attachment."""
    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=get_credentials())
    payload = _build_message(to, subject, body, file_path)
    result = service.users().messages().send(userId="me", body=payload).execute()
    label = f" + {Path(file_path).name}" if file_path else ""
    print(f"✅ Sent{label}. Message ID: {result['id']}")
    return result


def reply_to_thread(thread_id: str, message_id: str, to: list,
                    subject: str, body: str) -> dict:
    """Reply within an existing Gmail thread."""
    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=get_credentials())
    subj = f"Re: {subject}" if not subject.startswith("Re:") else subject
    payload = _build_message(to, subj, body, thread_id=thread_id, message_id=message_id)
    result = service.users().messages().send(userId="me", body=payload).execute()
    print(f"✅ Reply sent. Message ID: {result['id']}")
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gmail Advanced Utility for Claude")
    sub = parser.add_subparsers(dest="command")

    # attachments-list
    p = sub.add_parser("attachments-list")
    p.add_argument("--message-id", required=True)

    # attachments-download
    p = sub.add_parser("attachments-download")
    p.add_argument("--message-id", required=True)
    p.add_argument("--attachment-id", required=True)
    p.add_argument("--filename", required=True)
    p.add_argument("--save-dir", default="~/Downloads")

    # draft-with-attachment
    p = sub.add_parser("draft-with-attachment")
    p.add_argument("--to", required=True, help="Comma-separated recipients")
    p.add_argument("--subject", required=True)
    p.add_argument("--body", required=True)
    p.add_argument("--file", required=True)

    # send-with-attachment
    p = sub.add_parser("send-with-attachment")
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--body", required=True)
    p.add_argument("--file", required=True)

    # reply
    p = sub.add_parser("reply")
    p.add_argument("--thread-id", required=True)
    p.add_argument("--message-id", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--body", required=True)

    # send (plain)
    p = sub.add_parser("send")
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--body", required=True)

    args = parser.parse_args()

    def recipients(s):
        return [r.strip() for r in s.split(",")]

    if args.command == "attachments-list":
        list_attachments(args.message_id)
    elif args.command == "attachments-download":
        download_attachment(args.message_id, args.attachment_id, args.filename, args.save_dir)
    elif args.command == "draft-with-attachment":
        create_draft(recipients(args.to), args.subject, args.body, args.file)
    elif args.command == "send-with-attachment":
        send_email(recipients(args.to), args.subject, args.body, args.file)
    elif args.command == "reply":
        reply_to_thread(args.thread_id, args.message_id, recipients(args.to), args.subject, args.body)
    elif args.command == "send":
        send_email(recipients(args.to), args.subject, args.body)
    else:
        parser.print_help()
