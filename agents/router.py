"""
Router Agent
Routes classified emails to the appropriate support team
based on routing rules configuration.
"""

import os
import yaml


def load_routing_rules(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "config", "routing_rules.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def route_email(classification: dict) -> dict:
    """
    Determine routing based on classification result.

    Args:
        classification: dict with 'category', 'confidence', 'is_urgent'

    Returns:
        dict with 'assignment_group', 'priority', 'sla_hours'
    """
    rules = load_routing_rules()
    category = classification["category"]

    if category not in rules["categories"]:
        category = "general"

    rule = rules["categories"][category]
    priority = rule["priority"]

    # Bump priority if urgent or low confidence
    if classification.get("is_urgent"):
        priority = max(1, priority - 1)
    if classification.get("confidence", 1.0) < 0.7:
        priority = max(1, priority - 1)

    return {
        "assignment_group": rule["assignment_group"],
        "priority": priority,
        "sla_hours": rule["sla_hours"],
        "category": category,
    }


if __name__ == "__main__":
    test_classification = {
        "category": "connectivity",
        "confidence": 0.98,
        "summary": "VPN not connecting",
        "is_urgent": False,
    }

    result = route_email(test_classification)
    print(f"Route: {result}")
