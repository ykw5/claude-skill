#!/usr/bin/env python3
"""
gmail_reply_with_attachment.py
==============================
Fills the one gap left by gmail_advanced.py: a THREADED reply (draft or send)
that ALSO carries file attachments.

gmail_advanced.py can do:
  - reply (threaded)            -> no attachment
  - draft-with-attachment       -> attachment, but NOT threaded
  - send-with-attachment        -> attachment, but NOT threaded
...so "reply in a thread + attach a figure" needs this helper.

It reuses the same OAuth token as gmail_advanced.py
(~/claude-gmail/gmail-token.json) and supports MULTIPLE attachments.

Usage
-----
  # draft a threaded reply with two attachments (default = draft, not sent)
  python3 gmail_reply_with_attachment.py \
      --thread-id  19e2b453121f2bce \
      --message-id 19e3b4d179f5f903 \
      --to "a@x.com,b@y.com" \
      --subject "Re: ..." \
      --body "Reply text" \
      --file /path/fig1.pdf --file /path/fig2.pdf

  # same but actually send it
  python3 gmail_reply_with_attachment.py ... --send

Find thread-id / message-id with the Gmail MCP connector
(search_threads / get_thread) — they are hex strings like 19e2b453121f2bce.
"""
import argparse
import base64
import json
import mimetypes
import sys
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

TOKEN_FILE = Path.home() / "claude-gmail" / "gmail-token.json"


def get_credentials():
    if not TOKEN_FILE.exists():
        sys.exit(f"ERROR: token not found at {TOKEN_FILE}. Run gmail_setup.py first.")
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    data = json.loads(TOKEN_FILE.read_text())
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


def main():
    ap = argparse.ArgumentParser(description="Threaded Gmail reply (draft or send) with attachments")
    ap.add_argument("--thread-id", required=True, help="Gmail thread id (hex)")
    ap.add_argument("--message-id", required=True, help="Gmail message id of the message being replied to")
    ap.add_argument("--to", required=True, help="Comma-separated recipients")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--file", action="append", default=[], help="Path to a file to attach (repeatable)")
    ap.add_argument("--send", action="store_true", help="Send immediately instead of saving a draft")
    args = ap.parse_args()

    to = [r.strip() for r in args.to.split(",") if r.strip()]
    subject = args.subject if args.subject.startswith("Re:") else f"Re: {args.subject}"

    msg = MIMEMultipart()
    msg.attach(MIMEText(args.body, "plain"))
    for fp in args.file:
        p = Path(fp).expanduser()
        if not p.exists():
            sys.exit(f"ERROR: file not found: {p}")
        mime_type, _ = mimetypes.guess_type(str(p))
        main_type, sub_type = (mime_type.split("/", 1) if mime_type else ("application", "octet-stream"))
        part = MIMEBase(main_type, sub_type)
        part.set_payload(p.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=p.name)
        msg.attach(part)

    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg["In-Reply-To"] = args.message_id
    msg["References"] = args.message_id

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload = {"raw": raw, "threadId": args.thread_id}

    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=get_credentials())

    if args.send:
        res = service.users().messages().send(userId="me", body=payload).execute()
        print(f"Sent threaded reply with {len(args.file)} attachment(s). Message ID: {res['id']}")
    else:
        draft = service.users().drafts().create(userId="me", body={"message": payload}).execute()
        print(f"Draft (threaded reply) created with {len(args.file)} attachment(s). Draft ID: {draft['id']}")


if __name__ == "__main__":
    main()
