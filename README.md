# Spaminator

Small script that reads messages from Gmail and classifies them using Google's Gemini generative API.

Quick start

1. Create and activate a virtualenv (macOS zsh):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your Gemini/Generative API key:

```
GOOGLE_API_KEY=ya29.xxxxxxxxxxxxx
```

4. Obtain `credentials.json` (Google OAuth client secret) and place it in the repository root. The first run will create `token.json` after authorizing.

5. Run the classifier:

```bash
python read_inbox_and_classify.py
```

Security note

Do NOT commit `credentials.json`, `token.json`, or your `.env` file to any public repository. They contain secrets. This repo's default `.gitignore` excludes those files.

How to push to GitHub

1. Initialize a git repo if needed, add files and commit (this repo's scripts can help):

```bash
git init
git add .
git commit -m "Initial commit"
```

2. Create a GitHub repo via the website or the `gh` CLI and add the remote, then push:

```bash
git remote add origin git@github.com:<youruser>/spaminator.git
git branch -M main
git push -u origin main
```

If you want, I can create the remote for you if you have the `gh` CLI installed and are authenticated.
