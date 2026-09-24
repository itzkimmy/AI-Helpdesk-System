"""
Audit chain verification script.

Scans all tickets in the system and verifies the cryptographic SHA-256 hash chain
of every TicketEvent to ensure zero tampering.
"""

import logging
from app.models.ticket import Ticket
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


def run_verification(app=None):
    """Verify audit chain integrity across all tickets."""
    print("Verifying Ticket Audit Chain Integrity...")

    tickets = Ticket.query.all()
    if not tickets:
        print("  No tickets found in database.")
        return

    total_tickets = len(tickets)
    valid_chains = 0
    corrupted_chains = 0
    total_events = 0

    for ticket in tickets:
        is_valid, details = AuditService.verify_chain(ticket.id)
        event_count = details.get("event_count", 0)
        total_events += event_count

        if is_valid:
            valid_chains += 1
            print(f"  [OK] Ticket {ticket.ticket_number}: {event_count} event(s) verified.")
        else:
            corrupted_chains += 1
            print(f"  [FAIL] Ticket {ticket.ticket_number}: CORRUPTED AUDIT CHAIN!")
            for err in details.get("errors", []):
                print(f"    - Event #{err.get('event_id')}: {err.get('error')}")

    print("\nAudit Verification Summary:")
    print(f"  Total Tickets Checked: {total_tickets}")
    print(f"  Total Events Checked : {total_events}")
    print(f"  Valid Audit Chains  : {valid_chains}")
    print(f"  Corrupted Chains    : {corrupted_chains}")

    if corrupted_chains > 0:
        print("\nWARNING: Audit chain corruption detected!")
    else:
        print("\nSUCCESS: All audit chains intact.")


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        run_verification(app)
