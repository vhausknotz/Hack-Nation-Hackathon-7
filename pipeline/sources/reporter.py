"""NIH RePORTER API v2: funded research projects, their investigators and institutions."""

from dataclasses import dataclass

from http_cache import fetch_json

API = "https://api.reporter.nih.gov/v2/projects/search"


@dataclass
class Project:
    project_num: str
    title: str
    fiscal_year: int
    investigators: list[str]
    organization: str
    award_amount: int | None
    abstract: str
    url: str


def search(text: str, fiscal_years: list[int], limit: int = 200) -> tuple[int, list[Project]]:
    body = {
        "criteria": {
            "advanced_text_search": {"operator": "and", "search_field": "projecttitle,terms,abstracttext", "search_text": text},
            "fiscal_years": fiscal_years,
        },
        "include_fields": ["ProjectNum", "ProjectTitle", "FiscalYear", "PrincipalInvestigators", "Organization", "AwardAmount", "AbstractText", "ApplId"],
        "offset": 0,
        "limit": min(limit, 500),
        "sort_field": "fiscal_year",
        "sort_order": "desc",
    }
    data = fetch_json(API, body=body, min_interval=1.0)
    projects = [
        Project(
            project_num=r.get("project_num", ""),
            title=r.get("project_title", ""),
            fiscal_year=r.get("fiscal_year"),
            investigators=[pi.get("full_name", "") for pi in r.get("principal_investigators") or []],
            organization=(r.get("organization") or {}).get("org_name", ""),
            award_amount=r.get("award_amount"),
            abstract=r.get("abstract_text") or "",
            url=f"https://reporter.nih.gov/project-details/{r.get('appl_id')}",
        )
        for r in data.get("results", [])
    ]
    return data.get("meta", {}).get("total", len(projects)), projects
