"""
Email Monitor
Connects to Microsoft Graph API (Outlook) to read, send, and manage emails.
Uses MSAL device code flow for authentication.
"""

import os
import json
import re
import atexit

import msal
import requests


GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Mail.Read", "Mail.Send", "Mail.ReadWrite", "User.Read"]
TOKEN_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "token_cache.json")


_msal_app = None


def _build_msal_app():
    """Build an MSAL PublicClientApplication with persistent token cache (singleton)."""
    global _msal_app
    if _msal_app is not None:
        return _msal_app

    client_id = os.environ.get("MS_CLIENT_ID")
    authority = os.environ.get("MS_AUTHORITY", "https://login.microsoftonline.com/common")

    if not client_id:
        raise RuntimeError("MS_CLIENT_ID not set in .env — register an app at portal.azure.com")

    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_PATH):
        with open(TOKEN_CACHE_PATH, "r") as f:
            cache.deserialize(f.read())

    app = msal.PublicClientApplication(
        client_id,
        authority=authority,
        token_cache=cache,
    )

    def _save_cache():
        if cache.has_state_changed:
            with open(TOKEN_CACHE_PATH, "w") as f:
                f.write(cache.serialize())

    atexit.register(_save_cache)

    _msal_app = app
    return app


def authenticate():
    """
    Authenticate with Microsoft Graph via device code flow.
    First run: prints a URL + code for the user to sign in.
    Subsequent runs: uses cached/refreshed token silently.
    Returns an access token string.
    """
    app = _build_msal_app()

    # Try silent auth first (cached token)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            return result["access_token"]

    # Fall back to device code flow
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Device flow failed: {flow.get('error_description', 'unknown error')}")

    print()
    print("=" * 50)
    print("  MICROSOFT SIGN-IN REQUIRED")
    print("=" * 50)
    print(f"  1. Open:  {flow['verification_uri']}")
    print(f"  2. Enter: {flow['user_code']}")
    print("=" * 50)
    print()

    result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise RuntimeError(f"Authentication failed: {result.get('error_description', 'unknown error')}")

    return result["access_token"]


def get_user_info(token: str) -> dict:
    """Fetch the authenticated user's profile."""
    resp = requests.get(
        f"{GRAPH_BASE}/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _strip_html(html: str) -> str:
    """Strip HTML tags and collapse whitespace to get plain text."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


SKIP_SENDERS = {
    "noreply", "no-reply", "postmaster", "mailer-daemon",
    "account-security-noreply", "notifications", "member_services",
}

SKIP_DOMAINS = {
    "accountprotection.microsoft.com",
}


def _should_skip(address: str, subject: str) -> bool:
    """Check if an email should be skipped (system mail, auto-replies, newsletters)."""
    address = address.lower()
    local = address.split("@")[0]
    domain = address.split("@")[-1]

    # Skip known no-reply senders
    if local in SKIP_SENDERS:
        return True

    # Skip known system domains
    if domain in SKIP_DOMAINS:
        return True

    # Skip our own auto-replies
    if "[Ticket:" in subject:
        return True

    # Skip bounce-backs
    if subject.lower().startswith("undeliverable:"):
        return True

    return False


def fetch_unread_emails(token: str, max_count: int = 10) -> list[dict]:
    """
    Fetch unread emails from the user's inbox via Microsoft Graph.
    Skips system/no-reply emails. Returns a list of dicts in the project's internal email format.
    """
    resp = requests.get(
        f"{GRAPH_BASE}/me/messages",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "$filter": "isRead eq false",
            "$top": max_count,
            "$select": "id,from,subject,body,receivedDateTime",
            "$orderby": "receivedDateTime desc",
        },
        timeout=15,
    )
    resp.raise_for_status()
    messages = resp.json().get("value", [])

    emails = []
    for msg in messages:
        sender = msg.get("from", {}).get("emailAddress", {})
        body_content = msg.get("body", {}).get("content", "")
        body_type = msg.get("body", {}).get("contentType", "text")

        if body_type.lower() == "html":
            body_text = _strip_html(body_content)
        else:
            body_text = body_content

        address = sender.get("address", "unknown@unknown.com")
        subject = msg.get("subject", "")

        if _should_skip(address, subject):
            continue

        emails.append({
            "id": msg["id"],
            "from": address,
            "sender_name": sender.get("name", sender.get("address", "Unknown")),
            "subject": msg.get("subject", "(no subject)"),
            "body": body_text,
            "timestamp": msg.get("receivedDateTime", ""),
        })

    return emails


def mark_as_read(token: str, message_id: str):
    """Mark an email as read in Outlook."""
    resp = requests.patch(
        f"{GRAPH_BASE}/me/messages/{message_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"isRead": True},
        timeout=10,
    )
    resp.raise_for_status()


def send_reply(token: str, to: str, subject: str, body_html: str):
    """Send an email via Microsoft Graph."""
    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body_html,
            },
            "toRecipients": [
                {"emailAddress": {"address": to}}
            ],
        },
        "saveToSentItems": True,
    }

    resp = requests.post(
        f"{GRAPH_BASE}/me/sendMail",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()


# ── Standalone testing ──────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("Testing Microsoft Graph API connection...\n")

    token = authenticate()
    user = get_user_info(token)
    print(f"Authenticated as: {user.get('displayName')} ({user.get('mail') or user.get('userPrincipalName')})\n")

    print("Fetching unread emails...")
    emails = fetch_unread_emails(token, max_count=5)

    if not emails:
        print("  No unread emails found.")
    else:
        for i, email in enumerate(emails, 1):
            print(f"  [{i}] From: {email['from']}")
            print(f"       Subject: {email['subject']}")
            print(f"       Body preview: {email['body'][:100]}...")
            print()

    print("Sending test email...")
    my_email = user.get("mail") or user.get("userPrincipalName")
    send_reply(
        token,
        to=my_email,
        subject="Email Triage AI - Test",
        body_html="<p>This is a test email from the Email Triage AI system.</p>",
    )
    print(f"  Test email sent to {my_email}")
