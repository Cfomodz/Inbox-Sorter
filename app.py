import os
import re
import json
import time
from datetime import datetime
from flask import Flask, redirect, url_for, session, render_template, jsonify, request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# OAuth2 config
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

# Cache config
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')
CACHE_FILE = os.path.join(CACHE_DIR, 'emails.json')

# Fetch config
EMAILS_PER_FETCH = 1000  # Fetch 1000 at a time
BATCH_SIZE = 40  # API calls before pausing
BATCH_DELAY = 1.0  # seconds between batches

# Allow HTTP for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
# Allow scope changes (Google may return additional scopes)
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'


def ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def load_cache():
    """Load cached email data."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return None


def save_cache(data):
    """Save email data to cache."""
    ensure_cache_dir()
    data['cached_at'] = datetime.now().isoformat()
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f)


def clear_cache():
    """Clear cached data."""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)


def extract_email_domain(email_string):
    """Extract domain from email address."""
    match = re.search(r'<([^>]+)>', email_string)
    if match:
        email = match.group(1)
    else:
        email = email_string.strip()
    
    if '@' in email:
        return email.split('@')[1].lower()
    return 'unknown'


def extract_sender_name(email_string):
    """Extract sender name from email header."""
    match = re.search(r'^([^<]+)<', email_string)
    if match:
        return match.group(1).strip().strip('"')
    return email_string.split('@')[0] if '@' in email_string else email_string


def get_header_value(headers, name):
    """Get header value by name."""
    for header in headers:
        if header['name'].lower() == name.lower():
            return header['value']
    return ''


def merge_domains(existing_domains, new_emails_by_domain):
    """Merge new email data into existing domain structure."""
    # Convert list to dict for easier merging
    domains_dict = {d['domain']: d for d in existing_domains}
    
    for domain, data in new_emails_by_domain.items():
        if domain in domains_dict:
            # Merge emails, avoiding duplicates by ID
            existing_ids = {e['id'] for e in domains_dict[domain]['emails']}
            for email in data['emails']:
                if email['id'] not in existing_ids:
                    domains_dict[domain]['emails'].append(email)
                    domains_dict[domain]['count'] += 1
        else:
            domains_dict[domain] = data
    
    # Sort by count descending
    return sorted(domains_dict.values(), key=lambda x: x['count'], reverse=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/auth')
def auth():
    """Start OAuth2 flow."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return jsonify({'error': 'GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env'}), 400
    
    redirect_uri = 'http://localhost:3000/api/auth/callback/google'
    
    client_config = {
        'web': {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': [redirect_uri]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)


@app.route('/api/auth/callback/google')
def oauth2callback():
    """Handle OAuth2 callback."""
    redirect_uri = 'http://localhost:3000/api/auth/callback/google'
    
    client_config = {
        'web': {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': [redirect_uri]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=session['state'],
        redirect_uri=redirect_uri
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    return redirect(url_for('index'))


@app.route('/check-auth')
def check_auth():
    """Check if user is authenticated and if cache exists."""
    cached = load_cache()
    return jsonify({
        'authenticated': 'credentials' in session,
        'has_cache': cached is not None,
        'cached_at': cached.get('cached_at') if cached else None,
        'cached_total': cached.get('total') if cached else 0,
        'has_more': cached.get('next_page_token') is not None if cached else False
    })


@app.route('/logout')
def logout():
    """Clear session and cache."""
    session.clear()
    clear_cache()
    return redirect(url_for('index'))


@app.route('/clear-cache')
def clear_cache_route():
    """Clear cached emails without logging out."""
    clear_cache()
    return jsonify({'success': True})


@app.route('/get-cached')
def get_cached():
    """Return cached emails if available."""
    cached = load_cache()
    if cached:
        return jsonify(cached)
    return jsonify({'error': 'No cached data'}), 404


@app.route('/fetch-emails')
def fetch_emails():
    """Fetch up to 1000 emails. Use load_more=true to continue from last position."""
    if 'credentials' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    credentials = Credentials(**session['credentials'])
    service = build('gmail', 'v1', credentials=credentials)
    
    # Check if we're loading more or starting fresh
    load_more = request.args.get('load_more', 'false') == 'true'
    cached = load_cache() if load_more else None
    
    # Get the page token if continuing
    page_token = cached.get('next_page_token') if cached else None
    
    # Get message IDs from inbox
    messages = []
    fetched_pages = 0
    
    while len(messages) < EMAILS_PER_FETCH:
        results = service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            maxResults=min(100, EMAILS_PER_FETCH - len(messages)),
            pageToken=page_token
        ).execute()
        
        if 'messages' in results:
            messages.extend(results['messages'])
        
        page_token = results.get('nextPageToken')
        fetched_pages += 1
        
        if not page_token:
            break
        
        time.sleep(0.1)
    
    # Fetch details for each message with rate limiting
    emails_by_domain = {}
    
    for i, msg in enumerate(messages):
        try:
            msg_data = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            
            headers = msg_data.get('payload', {}).get('headers', [])
            from_header = get_header_value(headers, 'From')
            subject = get_header_value(headers, 'Subject')
            date = get_header_value(headers, 'Date')
            
            domain = extract_email_domain(from_header)
            sender_name = extract_sender_name(from_header)
            
            if domain not in emails_by_domain:
                emails_by_domain[domain] = {
                    'domain': domain,
                    'count': 0,
                    'emails': []
                }
            
            emails_by_domain[domain]['count'] += 1
            emails_by_domain[domain]['emails'].append({
                'id': msg['id'],
                'from': from_header,
                'sender_name': sender_name,
                'subject': subject or '(No Subject)',
                'date': date,
                'snippet': msg_data.get('snippet', '')
            })
            
            # Rate limiting
            if (i + 1) % BATCH_SIZE == 0 and i + 1 < len(messages):
                time.sleep(BATCH_DELAY)
                
        except Exception as e:
            print(f"Error fetching message {msg['id']}: {e}")
            if 'rateLimitExceeded' in str(e) or '429' in str(e):
                time.sleep(5)
            continue
    
    # Merge with existing cache if loading more
    if cached and load_more:
        merged_domains = merge_domains(cached.get('domains', []), emails_by_domain)
        total = cached.get('total', 0) + len(messages)
    else:
        merged_domains = sorted(
            emails_by_domain.values(),
            key=lambda x: x['count'],
            reverse=True
        )
        total = len(messages)
    
    result = {
        'total': total,
        'domains': merged_domains,
        'next_page_token': page_token,
        'has_more': page_token is not None,
        'fetched_this_batch': len(messages)
    }
    
    save_cache(result)
    
    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True, port=3000)
