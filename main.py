"""
AI Email Triage & Ticket Automation System
Monitors email, classifies with AI, creates tickets, sends acknowledgements.
"""

import json
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from agents.orchestrator import pipeline
from db.audit import init_db, get_all_logs

POLL_INTERVAL = 30  # seconds between inbox checks in live mode


def load_sample_emails(path="tests/sample_emails.json"):
    with open(path, "r") as f:
        return json.load(f)


def print_summary():
    """Print the processing summary from the audit log."""
    print()
    print("=" * 60)
    print("  PROCESSING COMPLETE — SUMMARY")
    print("=" * 60)
    print()

    logs = get_all_logs()
    if not logs:
        print("  No emails processed yet.")
        return

    print(f"{'Email':<40} {'Category':<15} {'Team':<20} {'Ticket':<15}")
    print("-" * 90)
    for log in reversed(logs):
        print(f"{log['subject'][:39]:<40} {log['category']:<15} {log['assignment_group']:<20} {log['ticket_id']:<15}")


def run_sample_mode():
    """Process hardcoded sample emails (default mode)."""
    emails = load_sample_emails()
    print(f"Loaded {len(emails)} emails for processing.\n")

    results = []
    for i, email in enumerate(emails, 1):
        print(f"[Email {i}/{len(emails)}] {email['subject']}")
        print(f"  From: {email['from']}")
        print()

        state = pipeline.invoke({"email": email})
        results.append(state)
        print()

    print_summary()


def run_live_mode():
    """Authenticate with Microsoft Graph and poll for unread emails."""
    from agents.email_monitor import authenticate, get_user_info, fetch_unread_emails
    from agents.resolution_checker import check_resolved_tickets

    print("Authenticating with Microsoft Graph...")
    token = authenticate()

    user = get_user_info(token)
    user_email = user.get("mail") or user.get("userPrincipalName")
    print(f"Authenticated as: {user.get('displayName')} ({user_email})\n")

    print(f"Polling for unread emails every {POLL_INTERVAL}s. Press Ctrl+C to stop.\n")

    try:
        while True:
            # Re-authenticate to refresh token if needed
            token = authenticate()

            emails = fetch_unread_emails(token)

            if not emails:
                print(f"  No unread emails. Waiting {POLL_INTERVAL}s...")
            else:
                print(f"Found {len(emails)} unread email(s).\n")

                for i, email in enumerate(emails, 1):
                    print(f"[Email {i}/{len(emails)}] {email['subject']}")
                    print(f"  From: {email['from']}")
                    print()

                    state = pipeline.invoke({
                        "email": email,
                        "live_mode": True,
                        "graph_token": token,
                    })
                    print()

                print_summary()

            # Check for resolved tickets and send notifications
            check_resolved_tickets(token)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n\nStopping live monitor.")
        print_summary()


def main():
    print("=" * 60)
    print("  AI Email Triage & Ticket Automation System")
    print("=" * 60)
    print()

    init_db()

    live_mode = "--live" in sys.argv

    if live_mode:
        print("  Mode: LIVE (Microsoft Graph / Outlook)\n")
        run_live_mode()
    else:
        print("  Mode: SAMPLE (tests/sample_emails.json)\n")
        run_sample_mode()


if __name__ == "__main__":
    main()
