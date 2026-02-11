"""
Classification Agent
Uses Claude API to classify incoming emails into categories
with confidence scores.
"""

import os
import json
import anthropic


CLASSIFICATION_PROMPT = """You are an IT support email classifier. Analyze the email below and classify it into exactly ONE category.

CATEGORIES:
- connectivity: Network, VPN, internet, Wi-Fi, firewall, DNS, or connection issues
- onboarding: New hire setup, account creation, access requests, equipment provisioning
- transactional: Password resets, software installs, license requests, routine IT changes
- general: Uncategorized, multi-topic, policy questions, or anything that doesn't fit above

RULES:
- Pick the BEST single category
- Provide a confidence score from 0.0 to 1.0
- Extract a brief summary (1 sentence)
- If the email mentions urgency, flag it

Respond ONLY with valid JSON in this exact format:
{{
  "category": "connectivity|onboarding|transactional|general",
  "confidence": 0.95,
  "summary": "Brief one-sentence summary of the issue",
  "is_urgent": false
}}

EMAIL:
From: {sender}
Subject: {subject}

{body}
"""


def classify_email(email: dict) -> dict:
    """
    Classify an email using Claude API.

    Args:
        email: dict with keys 'from', 'subject', 'body'

    Returns:
        dict with 'category', 'confidence', 'summary', 'is_urgent'
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = CLASSIFICATION_PROMPT.format(
        sender=email["from"],
        subject=email["subject"],
        body=email["body"],
    )

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Strip markdown code fences if present
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]  # remove first line
        response_text = response_text.rsplit("```", 1)[0]  # remove last fence
        response_text = response_text.strip()

    result = json.loads(response_text)

    return {
        "category": result["category"],
        "confidence": result["confidence"],
        "summary": result["summary"],
        "is_urgent": result.get("is_urgent", False),
    }


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    test_email = {
        "from": "john@company.com",
        "subject": "VPN not connecting",
        "body": "I can't connect to the VPN from home. Getting timeout errors.",
    }

    result = classify_email(test_email)
    print(json.dumps(result, indent=2))
