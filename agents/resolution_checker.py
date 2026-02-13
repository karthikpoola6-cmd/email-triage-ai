"""
Resolution Checker Agent
Polls ServiceNow for resolved tickets and sends resolution notifications
to the original email sender via Microsoft Graph.
"""

import os

import requests
from jinja2 import Environment, FileSystemLoader

from agents.email_monitor import send_reply
from db.audit import get_unnotified_tickets, mark_resolution_notified


TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "config", "templates")


def _get_ticket_state(ticket_id: str) -> dict | None:
    """
    Query ServiceNow for a specific incident's state and resolution notes.
    Returns dict with 'state' and 'close_notes', or None on error.
    """
    instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
    username = os.getenv("SERVICENOW_USERNAME")
    password = os.getenv("SERVICENOW_PASSWORD")

    url = f"{instance_url}/api/now/table/incident"
    params = {
        "sysparm_query": f"number={ticket_id}",
        "sysparm_fields": "state,close_notes,number",
        "sysparm_limit": 1,
    }

    try:
        resp = requests.get(
            url,
            params=params,
            auth=(username, password),
            headers={"Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if results:
            return results[0]
    except Exception as e:
        print(f"        → ServiceNow query failed for {ticket_id}: {e}")

    return None


def generate_resolution_email(sender: str, sender_name: str, subject: str,
                               ticket_id: str, resolution_notes: str) -> dict:
    """Render the resolution notification email from the Jinja2 template."""
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("resolution_template.html")

    body_html = template.render(
        sender_name=sender_name,
        ticket_id=ticket_id,
        subject=subject,
        resolution_notes=resolution_notes or "Resolved by support team.",
    )

    return {
        "to": sender,
        "subject": f"Resolved: {subject} [Ticket: {ticket_id}]",
        "body_html": body_html,
    }


def check_resolved_tickets(token: str):
    """
    Check ServiceNow for resolved tickets and send resolution emails.
    Called each poll cycle in live mode.
    """
    unnotified = get_unnotified_tickets()
    if not unnotified:
        return

    print(f"  Checking {len(unnotified)} ticket(s) for resolution...")

    for entry in unnotified:
        ticket_id = entry["ticket_id"]

        if ticket_id.startswith("FAILED-"):
            mark_resolution_notified(ticket_id)
            continue

        ticket_data = _get_ticket_state(ticket_id)
        if not ticket_data:
            continue

        # State 6 = Resolved in ServiceNow
        if str(ticket_data.get("state")) == "6":
            close_notes = ticket_data.get("close_notes", "")
            sender = entry["sender"]
            # Use the sender's name from the email address if we don't have it stored
            sender_name = sender.split("@")[0].title()

            email_data = generate_resolution_email(
                sender=sender,
                sender_name=sender_name,
                subject=entry["subject"],
                ticket_id=ticket_id,
                resolution_notes=close_notes,
            )

            try:
                send_reply(
                    token,
                    to=email_data["to"],
                    subject=email_data["subject"],
                    body_html=email_data["body_html"],
                )
                mark_resolution_notified(ticket_id)
                print(f"        → Resolution notification sent for {ticket_id} to {sender}")
            except Exception as e:
                print(f"        → Failed to send resolution email for {ticket_id}: {e}")
