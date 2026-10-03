"""ClinicalTrials.gov API v2: studies matching a search term, flattened to the fields the atlas uses."""

from dataclasses import dataclass

from http_cache import fetch_json

API = "https://clinicaltrials.gov/api/v2/studies"


@dataclass
class Study:
    nct_id: str
    title: str
    status: str
    phases: list[str]
    study_type: str
    conditions: list[str]
    interventions: list[str]
    sponsor: str
    start: str
    enrollment: int | None
    eligibility: str
    url: str


def search(term: str, max_studies: int = 200) -> list[Study]:
    studies: list[Study] = []
    token = None
    while len(studies) < max_studies:
        params = {"query.term": term, "pageSize": 100, "format": "json"}
        if token:
            params["pageToken"] = token
        data = fetch_json(API, params, min_interval=0.3)
        for s in data.get("studies", []):
            p = s["protocolSection"]
            ident, status, design = p["identificationModule"], p.get("statusModule", {}), p.get("designModule", {})
            studies.append(Study(
                nct_id=ident["nctId"],
                title=ident.get("briefTitle", ""),
                status=status.get("overallStatus", ""),
                phases=design.get("phases", []),
                study_type=design.get("studyType", ""),
                conditions=p.get("conditionsModule", {}).get("conditions", []),
                interventions=[i.get("name", "") for i in p.get("armsInterventionsModule", {}).get("interventions", [])],
                sponsor=p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", ""),
                start=status.get("startDateStruct", {}).get("date", ""),
                enrollment=design.get("enrollmentInfo", {}).get("count"),
                eligibility=p.get("eligibilityModule", {}).get("eligibilityCriteria", ""),
                url=f"https://clinicaltrials.gov/study/{ident['nctId']}",
            ))
        token = data.get("nextPageToken")
        if not token:
            break
    return studies[:max_studies]
