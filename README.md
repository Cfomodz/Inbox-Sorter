# 📬 Inbox Sorter

A simple app that pulls your Gmail inbox and sorts emails by sender domain. See at a glance who's filling up your inbox.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0-green.svg)
![License](https://img.shields.io/badge/license-MIT-purple.svg)

<img width="3009" height="1917" alt="Screenshot_20251210_211222" src="https://github.com/user-attachments/assets/1d22a5b4-951a-4df1-85a0-dc0e9a3d2a47" />

## Features

- 🔐 Secure OAuth2 authentication (read-only access)
- 📊 Groups emails by sender domain
- 📈 Shows email count per domain, sorted by volume
- 🔍 Expandable cards to browse individual emails
- 📦 Local caching — fetched emails persist between sessions
- ⚡ Paginated fetching — 1,000 emails at a time, load more as needed

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Cfomodz/Inbox-Sorter.git
cd Inbox-Sorter
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set Up Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Gmail API**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "Gmail API" and enable it
4. Configure OAuth consent screen:
   - Go to "APIs & Services" → "OAuth consent screen"
   - Choose "External" user type
   - Fill in app name and contact emails
   - Add scope: `https://www.googleapis.com/auth/gmail.readonly`
   - Add your email as a test user (required while in testing mode)
5. Create credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Choose "Web application"
   - Add authorized redirect URI: `http://localhost:3000/api/auth/callback/google`
   - Copy the Client ID and Client Secret

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
SECRET_KEY=generate-a-random-secret-key
```

### 4. Run

```bash
python app.py
```

Open http://localhost:3000 in your browser.

## Usage

1. Click **Sign in with Google**
2. Authorize the app (read-only access)
3. Click **Fetch First 1,000** to load your first batch
4. View results sorted by sender domain
5. Click **Load 1,000 More** to fetch additional emails
6. Click any domain card to expand and see individual emails
7. Use **Clear Cache** to start fresh or **Sign Out** when done

## How It Works

- Fetches emails in batches of 1,000 with rate limiting to avoid API limits
- Each batch takes ~3-5 minutes depending on your connection
- Results are cached locally in `cache/emails.json`
- Returning to the app loads cached data instantly
- "Load More" continues from where you left off

## Security

- **Read-only access**: The app only requests permission to read emails, never modify or delete
- **Local caching**: Emails are cached on your machine only, never sent to external servers
- **Session-based**: OAuth credentials stored in browser session only
- **Cache cleared on logout**: Signing out removes all cached data

## Tech Stack

- **Backend**: Python, Flask
- **Auth**: Google OAuth 2.0
- **API**: Gmail API
- **Frontend**: Vanilla HTML/CSS/JS

## License

MIT
