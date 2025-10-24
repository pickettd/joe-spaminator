# auth_gmail.py
from __future__ import annotations
import os, json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Start read-only; later use gmail.modify when you want to change labels
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_creds():
    creds = None
    token_path = Path("token.json")
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=8181)
        token_path.write_text(creds.to_json())
    return creds


if __name__ == "__main__":
    c = get_creds()
    print("Authorization OK. Scopes:", c.scopes)
