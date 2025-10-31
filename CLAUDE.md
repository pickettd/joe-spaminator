# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Script-based Gmail email classifier using Google's Gemini API to identify spam. Two main components:
- `auth_gmail.py`: OAuth credential management
- `read_inbox_and_classify.py`: Main flow - fetches inbox messages, classifies via Gemini

## Development Setup

This project uses `uv` for dependency management:

```bash
# Install dependencies
uv pip install -r requirements.txt

# Format Python code
uv run ruff format
```

Traditional virtualenv also supported:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Required Secrets

Before running, you need:

### Gmail Authentication
Choose one of two authentication modes:

**File-based (default)**:
1. `credentials.json` - Google OAuth client secret (place in repo root)
2. First run creates `token.json` after OAuth authorization
3. Set `GMAIL_AUTH_MODE=file` in `.env` (or omit, as this is the default)

**Environment variable-based**:
1. `GMAIL_TOKEN_JSON` - Contents of token.json as a JSON string in `.env`
2. Set `GMAIL_AUTH_MODE=env` in `.env`
3. Useful for deployments where file access is restricted (e.g., containers, serverless)

### API Keys
Add to your `.env` file:
   - `GOOGLE_API_KEY=ya29.xxxxxxxxxxxxx` (for Gemini)
   - `OPENAI_API_KEY=sk-xxxxxxxxxxxxx` (for OpenAI, optional)
   - `OPENAI_BASE_URL=https://api.openai.com/v1` (for OpenAI, optional - only needed for custom endpoints)
   - `OPENAI_MODEL=gpt-4o-mini` (for OpenAI, optional - defaults to gpt-4o-mini)
   - `OPENAI_RESPONSE_FORMAT=json_object` (for OpenAI, optional - options: `json_object` (default), `json_schema` (for LM Studio), `text`, or `false`)

**NEVER commit credentials.json, token.json, or .env** - they're in `.gitignore`.

## Running the Classifier

```bash
# Use Gemini (default)
python read_inbox_and_classify.py

# Use OpenAI
python read_inbox_and_classify.py --api openai

# Show help
python read_inbox_and_classify.py --help
```

This fetches recent inbox messages (default: `in:inbox newer_than:7d`, max 10) and classifies each as SPAM or NOT_SPAM.

### Getting GMAIL_TOKEN_JSON for Environment-based Auth

To use environment variable authentication:

1. First, generate `token.json` using file-based auth:
   ```bash
   python auth_gmail.py
   ```

2. Copy the contents of `token.json` and add to `.env` as a single-line string:
   ```bash
   GMAIL_TOKEN_JSON='{"token": "...", "refresh_token": "...", "token_uri": "...", "client_id": "...", "client_secret": "...", "scopes": ["..."]}'
   ```

3. Set the auth mode:
   ```bash
   GMAIL_AUTH_MODE=env
   ```

4. Run the classifier - it will use the environment variable instead of the file.

## Code Architecture

### Authentication Flow (`auth_gmail.py`)
Two authentication modes available:

**File-based (`get_creds_from_file`)**:
- Uses `token.json` and `credentials.json` files
- Handles OAuth flow, token refresh, and writes updated tokens to disk
- Current scope: `gmail.readonly` (comment notes `gmail.modify` for label changes)

**Environment variable-based (`get_creds_from_env`)**:
- Uses `GMAIL_TOKEN_JSON` environment variable
- Handles token refresh and prints updated token for user to save
- No file I/O - useful for containerized/serverless deployments

**Main function (`get_creds`)**:
- Takes `use_env` parameter (controlled by `GMAIL_AUTH_MODE` env var)
- Routes to appropriate authentication method

### Classification Flow (`read_inbox_and_classify.py`)
1. `list_message_ids()`: Query Gmail for message IDs
2. `get_message_meta()`: Fetch headers (From, Subject, Date) + snippet
3. `get_plaintext_body()`: Recursively walk MIME parts for text/plain content
4. `classifier()`: Two-stage classification:
   - **Stage 1**: Hard local rules (thegivingblock.com domain, survey keywords, salesy phrases)
   - **Stage 2**: Gemini REST API fallback with strict JSON schema

### LLM Integration (Configurable)
The classifier supports two API providers via `--api` flag:

**Gemini** (default):
- Uses REST API (`v1beta/models/gemini-2.0-flash:generateContent`)
- Custom `gemini_generate_json()` function
- Requires `GOOGLE_API_KEY` in `.env`

**OpenAI**:
- Uses official `openai` Python client
- Model: Configurable via `OPENAI_MODEL` (defaults to `gpt-4o-mini`)
- Custom `openai_generate_json()` function
- Requires `OPENAI_API_KEY` in `.env`
- Optional `OPENAI_BASE_URL` for custom endpoints (e.g., OpenAI-compatible APIs like LM Studio, Ollama with openai-compatible server, etc.)
- Optional `OPENAI_MODEL` to specify which model to use (useful for testing different models or local models)
- Optional `OPENAI_RESPONSE_FORMAT` to control JSON formatting:
  - `json_object` (default): OpenAI's standard JSON mode
  - `json_schema`: Provides explicit schema for strict validation (required by LM Studio and some local models)
  - `text`: Plain text response (relies on regex JSON extraction)
  - `false`: Disables response_format parameter entirely

Both implementations:
- Use `SYSTEM_RULES` for classification instructions
- Expect JSON response: `{"label":"SPAM|NOT_SPAM","reason":"10-25 words"}`
- Include fallback regex extraction for malformed responses
- Use `temperature=0` for deterministic results

## Key Configuration

- `MAX_BODY_CHARS = 2000`: Limits message body sent to LLM to control costs
- `SALES_PHRASES`: List of trigger words for local classification
- `SCOPES`: OAuth scopes (currently read-only)
- `_API_PROVIDER`: Set via `--api` flag (gemini or openai)

## Common Modifications

**Change query parameters**: Edit `list_message_ids()` call in `main()`:
```python
ids = list_message_ids(_SERVICE, q="in:inbox newer_than:7d", max_results=10)
```

**Add hard classification rules**: Update the hard rules section in `classifier()` or add phrases to `SALES_PHRASES`

**Enable label modification**: Change `SCOPES` in `auth_gmail.py` to include `gmail.modify` and delete `token.json` to reauthorize

**Adjust Gemini behavior**: Modify `SYSTEM_RULES` (used as system instruction)

## Testing Strategy

No tests present. To add:
- Mock `auth_gmail.get_creds()` for fake credentials
- Mock `service.users().messages().get/list` for Gmail API responses
- Mock Gemini REST calls in `gemini_generate_json()` for predictable classifications
