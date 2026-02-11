"""
Orchestrator
Uses LangGraph to chain all agents into a single pipeline:
  Email → Classify → Route → Create Ticket → Acknowledge → Log
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


def classify_node(state: PipelineState) -> dict:
    print(f"  [1/5] Classifying email...")
    classification = classify_email(state["email"])
    print(f"        → {classification['category']} ({classification['confidence']:.0%})")
    return {"classification": classification}


def route_node(state: PipelineState) -> dict:
    print(f"  [2/5] Routing...")
    routing = route_email(state["classification"])
    print(f"        → {routing['assignment_group']} (P{routing['priority']})")
    return {"routing": routing}


def ticket_node(state: PipelineState) -> dict:
    print(f"  [3/5] Creating ServiceNow ticket...")
    ticket_id = create_ticket(state["email"], state["classification"], state["routing"])
    return {"ticket_id": ticket_id}


def ack_node(state: PipelineState) -> dict:
    print(f"  [4/5] Generating acknowledgement...")
    ack = generate_ack(state["email"], state["classification"], state["routing"], state["ticket_id"])
    print(f"        → Reply to: {ack['to']}")
    return {"acknowledgement": ack}


def log_node(state: PipelineState) -> dict:
    print(f"  [5/5] Logging to audit database...")
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
    graph.add_node("log", log_node)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "route")
    graph.add_edge("route", "create_ticket")
    graph.add_edge("create_ticket", "acknowledge")
    graph.add_edge("acknowledge", "log")
    graph.add_edge("log", END)

    return graph.compile()


pipeline = build_pipeline()
