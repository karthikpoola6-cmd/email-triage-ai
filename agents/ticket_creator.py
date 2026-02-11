"""
Ticket Creator Agent
Creates incidents in ServiceNow via REST API.
"""

import os
import requests


def create_ticket(email: dict, classification: dict, routing: dict) -> str:
    """
    Create an incident in ServiceNow.

    Returns:
        ticket_id (str): The incident number (e.g., INC0010001)
    """
    instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
    username = os.getenv("SERVICENOW_USERNAME")
    password = os.getenv("SERVICENOW_PASSWORD")

    url = f"{instance_url}/api/now/table/incident"

    payload = {
        "short_description": f"[{classification['category'].upper()}] {email['subject']}",
        "description": (
            f"From: {email['from']}\n"
            f"Subject: {email['subject']}\n"
            f"Classification: {classification['category']} "
            f"(confidence: {classification['confidence']})\n"
            f"Summary: {classification['summary']}\n\n"
            f"Original Email:\n{email.get('body', '')}"
        ),
        "urgency": str(routing["priority"]),
        "assignment_group": routing["assignment_group"],
        "caller_id": email["from"],
    }

    response = requests.post(
        url,
        json=payload,
        auth=(username, password),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )

    if response.status_code == 201:
        result = response.json()["result"]
        ticket_id = result["number"]
        print(f"  Ticket created: {ticket_id}")
        return ticket_id
    else:
        print(f"  ServiceNow error ({response.status_code}): {response.text[:200]}")
        return f"FAILED-{response.status_code}"


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    test_email = {
        "from": "john@company.com",
        "subject": "VPN not connecting",
        "body": "Can't connect to VPN from home.",
    }
    test_classification = {
        "category": "connectivity",
        "confidence": 0.98,
        "summary": "VPN connection timeout from home office",
    }
    test_routing = {
        "assignment_group": "Network Support",
        "priority": 2,
        "sla_hours": 4,
    }

    ticket_id = create_ticket(test_email, test_classification, test_routing)
    print(f"Result: {ticket_id}")
