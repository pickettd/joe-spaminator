# read_inbox_and_classify.py
from __future__ import annotations
from typing import Dict, Any, List
from googleapiclient.discovery import build
from auth_gmail import get_creds
import base64
import os, textwrap
from tenacity import retry, wait_exponential, stop_after_attempt
from pathlib import Path
from dotenv import load_dotenv
import json
import requests

SALES_PHRASES = [
    "would you be interested", "quick call", "jump on a call", "book time",
    "schedule a call", "pick a time", "calendly.com", "calendar link",
    "case study", "pilot program", "free consultation", "special offer",
    "limited time", "intro ", " x ",  # e.g., "Intro Foo x Bar"
    "we help you", "we can book", "generate leads", "lead gen",
]

def looks_salesy(subject: str, snippet: str) -> bool:
    t = f"{subject} {snippet}".lower()
    return any(p in t for p in SALES_PHRASES)

def gemini_generate_json(payload: dict) -> dict:
    """Call Gemini v1beta REST and return parsed JSON {label, reason}."""
    api_key = os.environ["GOOGLE_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    body = {
        "system_instruction": {
            "role": "user",
            "parts": [{"text": SYSTEM_RULES}]
        },
        "generation_config": {"temperature": 0, "response_mime_type": "application/json"},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": json.dumps(payload, ensure_ascii=False)}
                ]
            }
        ],
    }

    r = requests.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=30)
    if r.status_code != 200:
        try:
            print("Gemini REST error:", r.status_code, r.json())
        except Exception:
            print("Gemini REST error:", r.status_code, r.text[:500])
        r.raise_for_status()

    data = r.json()
    text = (
        data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
    )
    try:
        return json.loads(text)
    except Exception:
        import re
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        print("Warning: model returned non-JSON:", text[:200])
        return {"label": "NOT_SPAM", "reason": "non-json response"}

# ---- Globals ----------------------------------------------------------------
_SERVICE = None  # will be set in main()
MAX_BODY_CHARS = 2000  # safe default for trimming long message bodies

# ---- Gemini setup ------------------------------------------------------------
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
SYSTEM_RULES = """
You are an email gate. Classify ONE email as SPAM or NOT_SPAM.

Hard rules (override everything):
- If sender domain contains "thegivingblock.com" → SPAM.
- If the email asks to rate an experience or complete a store/merchant survey → SPAM.
- If the email is cold outreach / sales solicitation (e.g., “intro X x Y”, “would you be interested”, “book a call”, Calendly links, “we help you <outcome>”, lead-gen) → SPAM.

Signals for sales/solicitations (weigh heavily):
- Phrases: "would you be interested", "quick call", "jump on a call", "book time", "schedule", "pick a time", "intro", "case study", "pilot", "free consultation", "special offer", "limited time".
- Mentions lead-gen or booking meetings; Calendly/Meet/Zoom links; “we help you reach…”.
- Marketing footers: "unsubscribe", "update preferences", "view in browser".

False-positive guards:
- Transactional receipts, codes, real ongoing threads/replies from known contacts, expected calendar invites.

Output:
Return exactly one JSON object on one line:
{"label":"SPAM|NOT_SPAM","reason":"10–25 words"}
No extra text.
""".strip()

# Require the API key to be present and fail early with a clear message.
API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set. Create a .env file or set the env var before running the script.")

def redact(text: str) -> str:
    return text.replace("\r", " ").replace("\n", " ").strip()

# ---- Gmail helpers -----------------------------------------------------------
def list_message_ids(service, q: str = "in:inbox", max_results: int = 20) -> List[str]:
    resp = service.users().messages().list(userId="me", q=q, maxResults=max_results).execute()
    return [m["id"] for m in resp.get("messages", [])]

def sender_matches(email_from: str, needles: list[str]) -> bool:
    f = (email_from or "").lower()
    return any(n in f for n in needles)

def get_message_meta(service, msg_id: str) -> Dict[str, Any]:
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="metadata",
        metadataHeaders=["From", "Subject", "Date"]
    ).execute()
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    return {
        "id": msg_id,
        "from": headers.get("From", ""),
        "subject": headers.get("Subject", ""),
        "date": headers.get("Date", ""),
        "snippet": msg.get("snippet", "")
    }

def get_plaintext_body(service=None, msg_id: str = "") -> str:
    """Return the plain-text body of an email."""
    service = service or _SERVICE
    if not service or not msg_id:
        return ""
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

    def walk(parts):
        for p in parts:
            if p.get("mimeType") == "text/plain" and "data" in p.get("body", {}):
                return base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="ignore")
            if "parts" in p:
                content = walk(p["parts"])
                if content:
                    return content
        return ""

    payload = msg.get("payload", {})
    if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
    return walk(payload.get("parts", [])) or ""

# ---- LLM classifier ----------------------------------------------------------
from typing import Tuple

@retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(3))
def classifier(email: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Returns (is_spam, reason).
    Order:
      1) Hard, local rules (deterministic & fast)
      2) Gemini fallback with strict JSON
    """
    frm   = email.get("from", "")
    subj  = (email.get("subject") or "").lower()
    snip  = (email.get("snippet") or "").lower()

    # --- 1) Hard rules (local)
    if sender_matches(frm, ["thegivingblock.com", "the giving block"]):
        return True, "Domain matches thegivingblock.com hard rule"

    survey_phrases = [
        "rate your experience", "how did we do", "tell us about your visit",
        "your recent purchase", "share your feedback", "survey",
    ]
    if any(p in subj for p in survey_phrases) or any(p in snip for p in survey_phrases):
        return True, "Post-purchase survey / rating request"

    if looks_salesy(email.get("subject",""), email.get("snippet","")):
        return True, "Sales outreach / booking language detected"

    # --- 2) LLM fallback (send minimal content; SYSTEM_RULES covers salesy too)
    body = redact(get_plaintext_body(msg_id=email.get("id", "")))[:MAX_BODY_CHARS]
    user_email = {
        "from": frm,
        "subject": email.get("subject", ""),
        "snippet": email.get("snippet", ""),
        "body": body,
    }

    obj = gemini_generate_json(user_email)
    label  = (obj.get("label") or "").upper()
    reason = obj.get("reason") or "Model classification"
    return (label == "SPAM", reason)

# ---- Main --------------------------------------------------------------------
def main():
    global _SERVICE
    _SERVICE = build("gmail", "v1", credentials=get_creds())

    ids = list_message_ids(_SERVICE, q="in:inbox newer_than:7d", max_results=10)
    for msg_id in ids:
        meta = get_message_meta(_SERVICE, msg_id)
        is_spam, reason = classifier(meta)
        tag = "SPAM ⛔" if is_spam else "legit ❎"
        print(f"[{tag}] {meta['date']} | {meta['from']} | {meta['subject']}")
        print(f"   reason: {reason}")
        print(f"   {meta['snippet'][:160]}{'…' if len(meta['snippet']) > 160 else ''}")


if __name__ == "__main__":
    main()
