"""
Acknowledgement Agent
Generates acknowledgement email responses using Jinja2 templates.
"""

import os
from jinja2 import Environment, FileSystemLoader


TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "config", "templates")


def generate_ack(email: dict, classification: dict, routing: dict, ticket_id: str) -> dict:
    """
    Generate an acknowledgement email response.

    Returns:
        dict with 'to', 'subject', 'body_html'
    """
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("ack_template.html")

    body_html = template.render(
        sender_name=email.get("sender_name", email["from"]),
        subject=email["subject"],
        category=classification["category"],
        ticket_id=ticket_id,
        assignment_group=routing["assignment_group"],
        sla_hours=routing["sla_hours"],
    )

    return {
        "to": email["from"],
        "subject": f"Re: {email['subject']} [Ticket: {ticket_id}]",
        "body_html": body_html,
    }


if __name__ == "__main__":
    test_email = {
        "from": "john@company.com",
        "sender_name": "John",
        "subject": "VPN not connecting",
    }
    test_classification = {"category": "connectivity"}
    test_routing = {"assignment_group": "Network Support", "sla_hours": 4}

    ack = generate_ack(test_email, test_classification, test_routing, "INC0010001")
    print(f"To: {ack['to']}")
    print(f"Subject: {ack['subject']}")
    print(f"Body:\n{ack['body_html']}")
