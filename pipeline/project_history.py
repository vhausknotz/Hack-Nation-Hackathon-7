"""Small public audit trails for the exact claims selected by the family projection.

Dates come from archived sources and recorded events, never the build date or a
contributor's self-reported creation date. No credentials or agent manifests are
exported. This is recorded provenance, not a fresh check of a live source.
"""
import json


def listing_history(store, claim_id: str, claim: dict) -> dict:
    events = [dict(e) for e in store.events_for(claim_id)]
    proposed = next((e["ts"] for e in events if e["type"] == "claim.proposed"), None)
    checked = next((e["ts"] for e in events if e["type"] == "kernel.checked"
                    and json.loads(e["payload"] or "{}").get("passed") is True), None)
    attestations = {e["id"]: e for e in events if e["type"] == "review.attested" and e["payload"]}
    reviews = []
    for row in store.reviews_for(claim_id):
        r = dict(row)
        event = attestations.get(r.get("event_id"))
        if event:
            reviews.append({"at": event["ts"], "kind": r["reviewer_kind"],
                            "model": r.get("model"), "family": r.get("model_family"),
                            "verdict": r["verdict"], "reason": r["reason"]})
    sources = []
    for source_id in dict.fromkeys(e["source_id"] for e in claim["evidence"] if e.get("source_id")):
        source = store.source(source_id)
        if source:
            sources.append({"id": source_id, "archived_at": source.get("retrieved"),
                            "url": source.get("url", "")})
    return {"submitted_at": proposed, "kernel_checked_at": checked, "sources": sources, "reviews": reviews}
