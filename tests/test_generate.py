import pytest
from agentci.data.generate import validate_tickets, validate_kb, TicketShapeError

def test_validate_tickets_requires_fields():
    good = [{"id": "t00", "question": "q", "gold_resolution": "a", "policy_id": "refund-policy"}]
    validate_tickets(good)  # no raise

def test_validate_tickets_rejects_missing_gold():
    with pytest.raises(TicketShapeError):
        validate_tickets([{"id": "t00", "question": "q"}])

def test_validate_kb_requires_unique_ids():
    with pytest.raises(TicketShapeError):
        validate_kb([{"id": "x", "title": "a", "body": "b"},
                     {"id": "x", "title": "c", "body": "d"}])
