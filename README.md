# Email Triage AI

An automated system that monitors a shared mailbox, classifies incoming IT support emails using AI, creates ServiceNow incidents, and sends acknowledgement replies. Built to solve the problem of IT teams manually sorting through hundreds of support emails per day.

## How It Works

1. The system connects to an Outlook mailbox through the Microsoft Graph API
2. It pulls unread emails and sends each one through a six step pipeline
3. Claude AI reads the email and classifies it into a category (connectivity, onboarding, transactional, or general) with a confidence score
4. Based on the category, it routes the email to the correct support team with an appropriate priority level
5. A ServiceNow incident is created automatically with all the relevant details
6. An acknowledgement email is sent back to the sender with their ticket number and expected response time
7. The original email is marked as read and the entire transaction is logged to an audit database

If the AI is unsure about a classification (confidence below 70%), the system bumps the priority so a human can review it faster rather than risking a wrong assignment.

## Architecture

The pipeline is built with LangGraph, which chains six agents together in sequence.

```
Incoming Email
      |
  Classifier (Claude AI)
      |
  Router (YAML rules)
      |
  Ticket Creator (ServiceNow API)
      |
  Acknowledger (Jinja2 template)
      |
  Email Sender (Microsoft Graph API)
      |
  Audit Logger (SQLite)
```

Each agent is a standalone module that does one thing. The orchestrator connects them into a state machine where each step passes its output to the next.

## Project Structure

```
agents/
    classifier.py        AI classification using Claude
    router.py            Rule based routing with priority escalation
    ticket_creator.py    ServiceNow incident creation
    acknowledger.py      HTML acknowledgement email generation
    email_monitor.py     Microsoft Graph API integration
    orchestrator.py      LangGraph pipeline that chains all agents

config/
    routing_rules.yaml   Category to team mapping with SLA definitions
    templates/
        ack_template.html    Jinja2 template for reply emails

db/
    audit.py             SQLite audit trail for all processed emails

tests/
    sample_emails.json   Test emails for offline development

main.py                  Entry point with sample and live modes
```

## Categories and Routing

| Category | Team | Default Priority | SLA |
|----------|------|-----------------|-----|
| Connectivity | Network Support | P2 | 4 hours |
| Onboarding | IT Onboarding | P3 | 24 hours |
| Transactional | Service Desk | P3 | 8 hours |
| General | General IT Support | P4 | 24 hours |

Priority is automatically bumped up when the email is flagged as urgent or when classification confidence is low.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Classification | Claude API (Anthropic) |
| Pipeline Orchestration | LangGraph |
| Email Integration | Microsoft Graph API with MSAL |
| Ticket Management | ServiceNow REST API |
| Template Rendering | Jinja2 |
| Routing Config | YAML |
| Audit Storage | SQLite |
| Language | Python 3.13 |

## Setup

### Prerequisites

Register an Azure app at portal.azure.com with delegated permissions for Mail.Read, Mail.Send, and Mail.ReadWrite. Enable public client flows in the authentication settings.

Create a ServiceNow developer instance at developer.servicenow.com.

Get an Anthropic API key at console.anthropic.com.

### Installation

```
git clone https://github.com/karthikpoola6-cmd/email-triage-ai.git
cd email-triage-ai
pip install -r requirements.txt
```

### Configuration

Create a `.env` file with the following values.

```
ANTHROPIC_API_KEY=your_anthropic_api_key
SERVICENOW_INSTANCE_URL=https://your_instance.service-now.com
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=your_password
MS_CLIENT_ID=your_azure_app_client_id
MS_AUTHORITY=https://login.microsoftonline.com/consumers
```

## Usage

### Sample Mode

Process test emails from the sample dataset. No external accounts needed.

```
python main.py
```

### Live Mode

Connect to a real Outlook mailbox and process incoming emails. On first run it will prompt you to sign in through a browser.

```
python main.py --live
```

The system polls for new unread emails every 30 seconds. Press Ctrl+C to stop.

## Sample Output

```
[Email 1/3] VPN not connecting from home
  From: user@company.com

  [1/6] Classifying email...
        → connectivity (98%)
  [2/6] Routing...
        → Network Support (P1)
  [3/6] Creating ServiceNow ticket...
        Ticket created: INC0010018
  [4/6] Generating acknowledgement...
        → Reply to: user@company.com
  [5/6] Sending reply via Outlook...
        → Sent to user@company.com
        → Marked original email as read
  [6/6] Logging to audit database...
        → Logged.
```
