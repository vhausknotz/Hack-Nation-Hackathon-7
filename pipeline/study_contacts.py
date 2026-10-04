"""Who runs each listed study: sponsor, lead investigators and public study contacts, from the official record.

    python pipeline/study_contacts.py          # fetch records for every family-visible study not yet cached

Mechanical extraction from ClinicalTrials.gov API v2 (public domain), no language model: the record's own
sponsor, overall officials, central contacts and site count. These are the public, professional routes a
study publishes for enquiries. Output: data/build/study_contacts.json (id -> team), refreshed when a study
appears or its cached copy is older than REFRESH_DAYS.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "build" / "study_contacts.json"
REFRESH_DAYS = 14
API = "https://clinicaltrials.gov/api/v2/studies/{}"


def team(study: dict) -> dict:
    p = study.get("protocolSection", {})
    sponsor = p.get("sponsorCollaboratorsModule", {})
    contacts = p.get("contactsLocationsModule", {})
    status = p.get("statusModule", {})
    responsible = sponsor.get("responsibleParty", {})
    officials = [{"name": o.get("name"), "affiliation": o.get("affiliation"), "role": (o.get("role") or "").replace("_", " ").lower()}
                 for o in contacts.get("overallOfficials", []) if o.get("name")][:4]
    if not officials and responsible.get("investigatorFullName"):
        officials = [{"name": responsible["investigatorFullName"], "affiliation": responsible.get("investigatorAffiliation"),
                      "role": "responsible investigator"}]
    central = [{"name": c.get("name"), "role": (c.get("role") or "").replace("_", " ").lower(), "email": c.get("email")}
               for c in contacts.get("centralContacts", []) if c.get("name") or c.get("email")][:3]
    locations = contacts.get("locations", [])
    return {
        "sponsor": (sponsor.get("leadSponsor") or {}).get("name"),
        "collaborators": [c["name"] for c in sponsor.get("collaborators", []) if c.get("name")][:5],
        "officials": officials,
        "contacts": central,
        "sites": len(locations),
        "countries": sorted({l["country"] for l in locations if l.get("country")})[:10],
        "updated": (status.get("lastUpdatePostDateStruct") or {}).get("date"),
    }


def listed_studies() -> set[str]:
    sys.path.insert(0, str(ROOT / "pipeline"))
    from project_actions import load_actions
    conditions = {c["id"]: c for c in map(json.loads, (ROOT / "data/build/conditions.jsonl").read_text(encoding="utf-8").splitlines()) if c}
    return {a["id"] for v in load_actions(conditions).values() for a in v.get("assets", []) if a["id"].startswith("NCT")}


def main() -> None:
    cache = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    now = datetime.now(timezone.utc)
    stale = lambda e: (now - datetime.fromisoformat(e["retrieved"])).days >= REFRESH_DAYS  # noqa: E731
    todo = sorted(nct for nct in listed_studies() if nct not in cache or stale(cache[nct]))
    for nct in todo:
        try:
            r = requests.get(API.format(nct), timeout=30)
            r.raise_for_status()
            cache[nct] = {**team(r.json()), "retrieved": now.isoformat(timespec="seconds"), "url": f"https://clinicaltrials.gov/study/{nct}"}
        except (requests.RequestException, ValueError) as e:
            print(f"{nct}: {e}", file=sys.stderr)
        time.sleep(0.4)
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"study teams: {len(cache)} cached, {len(todo)} fetched")


if __name__ == "__main__":
    main()
