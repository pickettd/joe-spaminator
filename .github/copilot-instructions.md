# Copilot instructions for this repo

Purpose: give an AI coding agent the minimum, concrete knowledge to be productive with this small Gmail+Gemini prototype.

Quick summary
- This repository is a small script-based project that reads Gmail messages and classifies them using Google's Gemini generative API.
- Key scripts: `read_inbox_and_classify.py` (main flow + LLM classifier) and `auth_gmail.py` (OAuth helper).

Key files and roles
- `auth_gmail.py` — obtains OAuth credentials and writes `token.json`. Uses scope `https://www.googleapis.com/auth/gmail.readonly` (comment notes `gmail.modify` if you want to change labels).
- `read_inbox_and_classify.py` — builds the Gmail service, lists recent inbox messages, fetches metadata and plaintext bodies, and calls Gemini to return SPAM/NOT_SPAM.
- `credentials.json` — expected to be the Google OAuth client secrets JSON (not checked into repo). `token.json` is created after first auth.

Environment & external integrations (explicit)
- dotenv: `read_inbox_and_classify.py` calls `load_dotenv()` and expects `GOOGLE_API_KEY` in the environment (or a `.env` file). This is used to configure `google.generativeai`.
- Google Gmail API: code uses `googleapiclient.discovery.build` with credentials from `auth_gmail.get_creds()`.
- Google Gemini (google-generativeai): configured via `genai.configure(api_key=...)` and a `GenerativeModel` is created (`gemini-1.5-flash`).

Quick start (developer / run steps you can execute locally)
1. Create and activate a virtualenv (macOS zsh):
   python3 -m venv .venv
   source .venv/bin/activate
2. Install the runtime dependencies (inferred from imports):
   pip install google-api-python-client google-auth google-auth-oauthlib python-dotenv google-generativeai tenacity
3. Obtain `credentials.json` from Google Cloud Console (OAuth client), place it in the repo root.
4. Create a `.env` with your generative API key, e.g. `GOOGLE_API_KEY=ya29.xxxxxx`.
5. Run the script (first run will open a browser to authorize):
   python read_inbox_and_classify.py

Developer patterns and conventions found in code
- Small, script-first codebase. Functions are procedural helpers (list_message_ids, get_message_meta, get_plaintext_body, classifier). Unit-test strategy: mock the Gmail service and the Gemini client calls.
- Email body extraction: `get_plaintext_body()` walks MIME parts recursively and prefers `text/plain` parts. Use this helper when adding features that need raw text.
- Metadata fetch: `get_message_meta()` requests `format='metadata'` with `metadataHeaders=['From','Subject','Date']` — the code expects those exact keys.
- LLM usage: `GEMINI_MODEL.generate_content()` is called with an array of roles/parts. The code expects a single-line JSON string response and does a simple text search for `"label":"SPAM"`.

Important gotchas / actionable notes (fixes or watch-for)
- `MAX_BODY_CHARS` is referenced in `read_inbox_and_classify.py` but not defined. This will raise a NameError at runtime — define it or remove the slice.
- The classifier's response parsing is fragile: it uppercases the entire response and searches for substrings to detect "SPAM". Prefer parsing JSON from the LLM output and validate shape: {"label":"SPAM","reason":"..."}.
- There are two near-duplicate system prompt blocks (module-level `SYSTEM_RULES` and `system_rules` inside `classifier`). Keep them in sync if you tune behavior.
- The script currently uses read-only Gmail scope. If you intend to modify labels, update `SCOPES` in `auth_gmail.py` to include `https://www.googleapis.com/auth/gmail.modify` and reauthorize.

Where to make common changes
- To change what messages are fetched, edit the query passed to `list_message_ids()` in `main()` (currently `in:inbox newer_than:7d`).
- To preview full message bodies while debugging, uncomment the two preview lines in `main()` under the print block.
- To harden the classifier for tests/dev, add a wrapper that accepts a prebuilt Gemini response or inject a mock `GEMINI_MODEL`.

Notes for tests and CI
- No tests or CI present. For quick unit tests: mock `auth_gmail.get_creds()` to return a fake credentials object and mock `service.users().messages().get/list` to return fixtures. Mock `GEMINI_MODEL.generate_content()` to return a predictable .text payload.

If anything in this file is unclear or you'd like me to expand examples (mock code, a small test harness, or a `requirements.txt`), tell me which part and I'll add it.
