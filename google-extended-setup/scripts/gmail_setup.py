#!/usr/bin/env python3
"""
One-time OAuth setup for Gmail Advanced Utility.

Usage:
    python3 gmail_setup.py --credentials ~/Downloads/client_secret_xxx.json

This opens a browser window for you to sign in with your Google account
and grant Gmail access. The resulting token is saved to:
    ~/claude-gmail/gmail-token.json

You only need to run this once. The token auto-refreshes.
"""

import argparse
import json
import sys
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
]

TOKEN_DIR = Path.home() / "claude-gmail"
TOKEN_FILE = TOKEN_DIR / "gmail-token.json"


def main():
    parser = argparse.ArgumentParser(description="Gmail OAuth setup")
    parser.add_argument(
        "--credentials", required=True,
        help="Path to client_secret_*.json downloaded from Google Cloud Console"
    )
    args = parser.parse_args()

    creds_path = Path(args.credentials).expanduser()
    if not creds_path.exists():
        print(f"ERROR: Credentials file not found: {creds_path}")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
    except ImportError:
        print("Installing required packages...")
        import subprocess
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "google-api-python-client",
            "google-auth-httplib2",
            "google-auth-oauthlib",
        ])
        from google_auth_oauthlib.flow import InstalledAppFlow

    print("\n🔐 Starting Gmail authorization...")
    print("A browser window will open. Sign in with your Google account and allow access.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))

    print(f"\n✅ Setup complete! Token saved to: {TOKEN_FILE}")
    print("You can now use gmail_advanced.py with Claude.\n")


if __name__ == "__main__":
    main()
