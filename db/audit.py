"""
Audit Log
SQLite database for tracking every email processed through the system.
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "audit.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT,
            sender TEXT,
            subject TEXT,
            category TEXT,
            confidence REAL,
            summary TEXT,
            is_urgent BOOLEAN,
            assignment_group TEXT,
            priority INTEGER,
            ticket_id TEXT,
            status TEXT DEFAULT 'processed',
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_event(email: dict, classification: dict, routing: dict, ticket_id: str = None):
    """Log a processed email to the audit database."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO audit_log
            (email_id, sender, subject, category, confidence, summary,
             is_urgent, assignment_group, priority, ticket_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            email.get("id", "unknown"),
            email.get("from", ""),
            email.get("subject", ""),
            classification["category"],
            classification["confidence"],
            classification["summary"],
            classification.get("is_urgent", False),
            routing["assignment_group"],
            routing["priority"],
            ticket_id,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_all_logs():
    """Retrieve all audit log entries."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")

    # Test insert
    log_event(
        email={"id": "test-001", "from": "test@test.com", "subject": "Test"},
        classification={"category": "general", "confidence": 0.9, "summary": "Test email", "is_urgent": False},
        routing={"assignment_group": "Service Desk", "priority": 3},
        ticket_id="INC0010001",
    )
    print("Test log entry created.")

    logs = get_all_logs()
    for log in logs:
        print(f"  [{log['created_at']}] {log['subject']} → {log['category']} → {log['ticket_id']}")
