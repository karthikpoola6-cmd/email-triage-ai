"""
AI Email Triage & Ticket Automation System
Monitors email, classifies with AI, creates tickets, sends acknowledgements.
"""

import json
from dotenv import load_dotenv

load_dotenv()

from agents.orchestrator import pipeline
from db.audit import init_db, get_all_logs


def load_sample_emails(path="tests/sample_emails.json"):
    with open(path, "r") as f:
        return json.load(f)


def main():
    print("=" * 60)
    print("  AI Email Triage & Ticket Automation System")
    print("=" * 60)
    print()

    init_db()

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

    # Summary
    print("=" * 60)
    print("  PROCESSING COMPLETE — SUMMARY")
    print("=" * 60)
    print()

    logs = get_all_logs()
    print(f"{'Email':<40} {'Category':<15} {'Team':<20} {'Ticket':<15}")
    print("-" * 90)
    for log in reversed(logs):
        print(f"{log['subject'][:39]:<40} {log['category']:<15} {log['assignment_group']:<20} {log['ticket_id']:<15}")


if __name__ == "__main__":
    main()
