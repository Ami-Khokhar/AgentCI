"""Knowledge-base accessor and the ADK tool the support agent calls."""
import json
from pathlib import Path

_FALLBACK_KB = [
    {
        "id": "refund-policy",
        "title": "Refund Policy",
        "body": "Customers may request a full refund within 14 days of a charge. "
                "Refunds require the subscription to be on a monthly plan; annual "
                "plans are prorated. Approved refunds post within 5 business days.",
    },
    {
        "id": "billing-cycle",
        "title": "Billing Cycle",
        "body": "Subscriptions renew on the calendar day of initial purchase. "
                "Invoices are emailed 3 days before renewal.",
    },
]

_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "kb.json"

# Common words carry no retrieval signal and (as bare substrings like "to"/"the")
# would spuriously match every KB section, so they are excluded from matching.
_STOP_WORDS = frozenset({
    "how", "to", "the", "a", "an", "of", "on", "in", "is", "it", "do", "does", "did",
    "for", "and", "or", "with", "my", "i", "can", "could", "would", "should",
    "what", "when", "where", "why", "who", "which", "are", "be", "this", "that",
})


def _load_kb() -> list[dict]:
    if _KB_PATH.exists():
        return json.loads(_KB_PATH.read_text(encoding="utf-8"))
    return _FALLBACK_KB


def _content_words(query: str) -> list[str]:
    """Lowercased query tokens with stop-words and very short tokens removed."""
    return [w for w in query.lower().split() if w not in _STOP_WORDS and len(w) > 2]


def lookup_kb(query: str) -> dict:
    """Retrieve knowledge-base sections relevant to a support query.

    Args:
        query (str): The user's question or keywords to search the KB for.

    Returns:
        dict: {"status": "success", "sections": [{"id","title","body"}, ...]}.
    """
    words = _content_words(query)
    sections = [
        s for s in _load_kb()
        if any(word in (s["title"] + " " + s["body"]).lower() for word in words)
    ]
    return {"status": "success", "sections": sections}
