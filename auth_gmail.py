# auth_gmail.py
from __future__ import annotations
import os, json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Start read-only; later use gmail.modify when you want to change labels
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_creds_from_file():
    """File-based authentication using token.json and credentials.json"""
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


def get_creds_from_env():
    """Environment variable-based authentication using GMAIL_TOKEN_JSON"""
    token_json = os.environ.get("GMAIL_TOKEN_JSON")
    if not token_json:
        raise RuntimeError(
            "GMAIL_TOKEN_JSON not set. Add the token JSON content to your .env file."
        )

    try:
        token_data = json.loads(token_json)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"GMAIL_TOKEN_JSON is not valid JSON: {e}")

    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Optionally print updated token for user to save back to env
        print("Token was refreshed. Updated token JSON:")
        print(creds.to_json())

    return creds


def get_creds(use_env=False):
    """
    Get Gmail credentials.

    Args:
        use_env: If True, use GMAIL_TOKEN_JSON from environment.
                 If False, use token.json file (default).
    """
    if use_env:
        return get_creds_from_env()
    else:
        return get_creds_from_file()


if __name__ == "__main__":
    c = get_creds()
    print("Authorization OK. Scopes:", c.scopes)
