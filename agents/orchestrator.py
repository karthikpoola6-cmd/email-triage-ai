"""
Orchestrator
Uses LangGraph to chain all agents into a single pipeline:
  Email → Classify → Route → Create Ticket → Acknowledge → [Send Reply] → Log
"""

from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from agents.classifier import classify_email
from agents.router import route_email
from agents.ticket_creator import create_ticket
from agents.acknowledger import generate_ack
from db.audit import init_db, log_event


class PipelineState(TypedDict):
    email: dict
    classification: dict
    routing: dict
    ticket_id: str
    acknowledgement: dict
    live_mode: bool
    graph_token: str


def classify_node(state: PipelineState) -> dict:
    print(f"  [1/6] Classifying email...")
    classification = classify_email(state["email"])
    print(f"        → {classification['category']} ({classification['confidence']:.0%})")
    return {"classification": classification}


def route_node(state: PipelineState) -> dict:
    print(f"  [2/6] Routing...")
    routing = route_email(state["classification"])
    print(f"        → {routing['assignment_group']} (P{routing['priority']})")
    return {"routing": routing}


def ticket_node(state: PipelineState) -> dict:
    print(f"  [3/6] Creating ServiceNow ticket...")
    ticket_id = create_ticket(state["email"], state["classification"], state["routing"])
    return {"ticket_id": ticket_id}


def ack_node(state: PipelineState) -> dict:
    print(f"  [4/6] Generating acknowledgement...")
    ack = generate_ack(state["email"], state["classification"], state["routing"], state["ticket_id"])
    print(f"        → Reply to: {ack['to']}")
    return {"acknowledgement": ack}


def send_ack_node(state: PipelineState) -> dict:
    """Send the acknowledgement email via Microsoft Graph (live mode only)."""
    if not state.get("live_mode"):
        print(f"  [5/6] Sending reply... skipped (sample mode)")
        return {}

    print(f"  [5/6] Sending reply via Outlook...")
    from agents.email_monitor import send_reply, mark_as_read

    ack = state["acknowledgement"]
    token = state.get("graph_token", "")

    try:
        send_reply(token, to=ack["to"], subject=ack["subject"], body_html=ack["body_html"])
        print(f"        → Sent to {ack['to']}")
    except Exception as e:
        print(f"        → Failed to send reply: {e}")

    # Mark the original email as read
    email_id = state["email"].get("id")
    if email_id and not email_id.startswith("test-"):
        mark_as_read(token, email_id)
        print(f"        → Marked original email as read")

    return {}


def log_node(state: PipelineState) -> dict:
    print(f"  [6/6] Logging to audit database...")
    log_event(state["email"], state["classification"], state["routing"], state["ticket_id"])
    print(f"        → Logged.")
    return {}


def build_pipeline() -> StateGraph:
    """Build and compile the LangGraph pipeline."""
    graph = StateGraph(PipelineState)

    graph.add_node("classify", classify_node)
    graph.add_node("route", route_node)
    graph.add_node("create_ticket", ticket_node)
    graph.add_node("acknowledge", ack_node)
    graph.add_node("send_ack", send_ack_node)
    graph.add_node("log", log_node)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "route")
    graph.add_edge("route", "create_ticket")
    graph.add_edge("create_ticket", "acknowledge")
    graph.add_edge("acknowledge", "send_ack")
    graph.add_edge("send_ack", "log")
    graph.add_edge("log", END)

    return graph.compile()


pipeline = build_pipeline()
