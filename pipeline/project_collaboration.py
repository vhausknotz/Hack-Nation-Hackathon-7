"""Find shared research records in the reviewed action projection.

This is an ID join, not a biological inference or a recommendation to combine
cohorts. Both condition-specific listings retain their own review and eligibility.
Never turn a neighbor's listing into eligibility for the starting condition.
"""
from collections import defaultdict

TYPES = {"natural_history_study": 0, "registry": 1, "biorepository": 2,
         "outcome_measure": 3, "biomarker": 4, "model": 5}
VISIBLE = {"reviewed", "independently_reviewed", "human_reviewed"}


def eligible(asset):
    review = asset.get("review", {})
    return (asset.get("type") in TYPES and review.get("status") in VISIBLE
            and review.get("verdict") in {"supports", "supports_with_qualification"})


def shared_research(conditions, actions, neighbors, limit=3):
    """Return small, deterministic routes, each backed by two reviewed claims."""
    by_asset = defaultdict(list)
    for cid, action in actions.items():
        if cid not in conditions:
            continue
        for asset in action.get("assets", []):
            if eligible(asset):
                by_asset[asset["id"]].append((cid, asset))
    result = {}
    for cid, action in actions.items():
        if cid not in conditions:
            continue
        near = {n["id"]: i for i, n in enumerate(neighbors.get(cid, {}).get("neighbors", [])[:20])}
        candidates = []
        for own in action.get("assets", []):
            if not eligible(own):
                continue
            for other_id, other in by_asset[own["id"]]:
                if other_id == cid or other["type"] != own["type"]:
                    continue  # disagreement over purpose is not a shared-asset route
                condition = conditions[other_id]
                if condition["gene"]["symbol"] == conditions[cid]["gene"]["symbol"]:
                    continue  # don't imply a cross-community bridge from a split label
                people = [o for o in actions[other_id].get("communities", [])
                          if o["kind"] == "patient_organization" and o["review"]["status"] in VISIBLE
                          and o["review"]["verdict"] in {"supports", "supports_with_qualification"}]
                route = {"asset_id": own["id"], "partner": {"id": other_id, "name": condition["name"],
                         "gene": condition["gene"]["symbol"]}, "partner_asset": other,
                         "partner_community": people[0] if people else None,
                         "basis": "same_reviewed_record", "is_computed_neighbor": other_id in near}
                rank = (TYPES[own["type"]], other_id not in near, near.get(other_id, 999),
                        not people, own["id"], other_id)
                candidates.append((rank, route))
        routes, seen = [], set()
        for _, route in sorted(candidates, key=lambda pair: pair[0]):
            key = route["partner"]["id"]
            if key in seen:
                continue
            seen.add(key)
            routes.append(route)
            if len(routes) >= limit:
                break
        if routes:
            result[cid] = routes
    return result
