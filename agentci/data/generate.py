"""ONE-SHOT generator: synthesize a SaaS-billing KB and 40 gold-resolution tickets.

Run by a human once; commit the resulting kb.json / tickets.json. Synthetic by design
(D7 / GAP-5) so the demo regression is scriptable and repeatable.

Usage:
    uv run python -m agentci.data.generate
"""
import json
from pathlib import Path

from google import genai

from agentci import config

_HERE = Path(__file__).resolve().parent


class TicketShapeError(ValueError):
    """Raised when generated data does not match the required schema."""


_REQUIRED_TICKET_FIELDS = {"id", "question", "gold_resolution", "policy_id"}


def validate_tickets(tickets: list[dict]) -> None:
    if len(tickets) < 1:
        raise TicketShapeError("no tickets")
    ids = set()
    for t in tickets:
        missing = _REQUIRED_TICKET_FIELDS - t.keys()
        if missing:
            raise TicketShapeError(f"ticket {t.get('id')} missing {missing}")
        if t["id"] in ids:
            raise TicketShapeError(f"duplicate ticket id {t['id']}")
        ids.add(t["id"])


def validate_kb(sections: list[dict]) -> None:
    ids = set()
    for s in sections:
        if not {"id", "title", "body"} <= s.keys():
            raise TicketShapeError(f"kb section missing fields: {s}")
        if s["id"] in ids:
            raise TicketShapeError(f"duplicate kb id {s['id']}")
        ids.add(s["id"])


_KB_PROMPT = """Generate a knowledge base for a SaaS billing product as JSON: a list of
8-12 objects with keys "id" (kebab-case), "title", "body" (2-4 sentences of concrete policy).
Cover at minimum: refund policy (14-day window, monthly-only eligibility, 5-business-day
posting), billing cycle, plan upgrades/downgrades, failed payments, cancellation, invoices,
seat management, tax/VAT. Return ONLY the JSON array."""


def _tickets_prompt(kb_json: str) -> str:
    return f"""Given this knowledge base JSON:\n{kb_json}\n
Generate 40 customer-support tickets as a JSON array. Each object has keys:
"id" ("t00".."t39"), "question" (a realistic customer message), "gold_resolution"
(the correct answer grounded ONLY in the KB, citing the relevant policy), and
"policy_id" (the KB section id the answer relies on). Spread questions across all KB
topics; include several refund-policy questions. Return ONLY the JSON array."""


def _gen(prompt: str) -> list[dict]:
    client = genai.Client()
    resp = client.models.generate_content(
        model=config.ENGINEER_MODEL,
        contents=prompt,
        config={"temperature": config.TEMPERATURE, "response_mime_type": "application/json"},
    )
    return json.loads(resp.text)


def main() -> None:
    kb = _gen(_KB_PROMPT)
    validate_kb(kb)
    (_HERE / "kb.json").write_text(json.dumps(kb, indent=2), encoding="utf-8")

    tickets = _gen(_tickets_prompt(json.dumps(kb)))
    validate_tickets(tickets)
    (_HERE / "tickets.json").write_text(json.dumps(tickets, indent=2), encoding="utf-8")
    print(f"wrote {len(kb)} KB sections and {len(tickets)} tickets")


if __name__ == "__main__":
    main()
