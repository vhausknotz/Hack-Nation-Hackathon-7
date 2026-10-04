"""Check the family journey and the research-question brief on a local preview, at desktop and phone widths.

python tools/check_family_brief.py http://localhost:4173 data/build/family-brief-qa

For STXBP1, SNAP25, Hutchinson-Gilford progeria and a sparse condition (ARF3) it walks the six Directions
stops, opens the brief, copies it as text and compares that text with the exported bundle: every listed
group and study keeps its exact URL, read date and verbatim restriction; archived pages stay labeled; missing
evidence is stated as "not yet found in the atlas". It also checks the ?brief=1 link (other parameters kept,
Back and Escape close it), print mode, horizontal overflow and wording that would imply a recommendation.
Screenshots and a printed PDF go to the output directory. Reads app/public/data; writes nothing else.
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

DATA = Path(__file__).resolve().parent.parent / "app" / "public" / "data"
CONDITIONS = {"stxbp1": "MONDO:0012812", "snap25": "MONDO:0014590", "hgps": "MONDO:0008310", "arf3": "MONDO:0700366"}
FORBIDDEN = [
    r"open to join", r"your next step this week", r"we recommend", r"you should (?:join|enroll|contact)",
    r"(?<!mean )(?<!means )you are eligible",r"(?:does not|doesn't|do not|don't) exist(?!s)", r"(?<!mean )\bno (?:patient )?(?:group|study|studies|research) exists",
]


def fnv1a(text: str) -> int:
    h = 0x811C9DC5
    for byte in text.encode("utf-8"):
        h = ((h ^ byte) * 0x01000193) & 0xFFFFFFFF
    return h


def bundle(cid: str) -> dict:
    return json.loads((DATA / "c" / f"{fnv1a(cid) % 256}.json").read_text(encoding="utf-8"))[cid]


def no_overflow(page: Page, where: str):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"page overflows horizontally: {where}"


def forbidden(text: str, where: str):
    for pattern in FORBIDDEN:
        hit = re.search(pattern, text, re.I)
        assert not hit, f"forbidden wording {hit.group(0)!r} in {where}"


def check_text(text: str, c: dict) -> int:
    """The copied brief against the bundle. Returns the number of listings verified."""
    # Windows clipboard APIs convert LF to CRLF. Normalize only that platform
    # encoding; every source character and internal line break must still match.
    text = text.replace("\r\n", "\n")
    orgs = [o for o in c.get("communities") or [] if o["kind"] in ("patient_organization", "research_program")]
    assets = c.get("assets") or []
    assert "It is not a recommendation" in text
    assert c["url"] in text, "diagnosis source URL missing"
    for o in orgs:
        assert o["homepage"] in text, f"homepage missing: {o['homepage']}"
        assert f"{o['page_date']}: {o['page'] or o['homepage']}" in text, f"source page/date missing: {o['name']}"
        assert o["review"]["reason"] in text, f"reviewer reason missing: {o['name']}"
        if o["page_read"] == "archived_snapshot":
            assert f"Archived source read {o['page_date']}" in text and f"only an archived copy of its page from {o['page_date']}" in text.lower(), f"archived label missing: {o['name']}"
    for a in assets:
        assert a["url"] in text, f"study URL missing: {a['url']}"
        if a["restriction"]:
            assert f"Restriction, as recorded: {a['restriction']}" in text, f"restriction not verbatim: {a['title']}"
        assert f"as recorded on {a['source_date']}" in text, f"study read date missing: {a['title']}"
        if a["type"] in ("trial", "therapy_program"):
            assert "not evidence that the treatment works" in text
    assert text.count("Listed, not recommended") >= len(orgs) + len(assets)
    if not any(o["kind"] == "patient_organization" for o in orgs):
        assert "No patient group for this diagnosis has been found in the atlas yet" in text
    if not assets:
        assert "No reviewed studies for this condition have been found in the atlas yet" in text
    if c["phenotype_count"] == 0:
        assert "No symptoms are recorded" in text
    if any(o["review"]["status"] == "reviewed" for o in orgs) or any(a["review"]["status"] == "reviewed" for a in assets):
        assert "one AI reviewer" in text
    forbidden(text, "brief text")
    return len(orgs) + len(assets)


def main(base: str, output: str):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (1440, 390):
            context = browser.new_context(viewport={"width": width, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
            page = context.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            for name, cid in CONDITIONS.items():
                c = bundle(cid)
                page.goto(f"{base}/c/{cid}", wait_until="networkidle")
                page.locator("button[aria-controls='stop-0']").wait_for()
                panel_text = []
                for step in range(6):
                    page.locator(f"button[aria-controls='stop-{step}']").click()
                    stop = page.locator(f"#stop-{step}")
                    assert stop.is_visible(), f"{name} stop {step + 1} not visible"
                    text = stop.text_content()  # not inner_text: headings are uppercased by CSS
                    panel_text.append(text)
                    if step == 3 and c.get("assets"):
                        assert "Registry reports" in text or "Recruitment status not recorded" in text
                    if step == 4:
                        assert "Nothing here is a recommendation" in text and "Prepare one question for your care team" in text
                    stop.scroll_into_view_if_needed()
                    no_overflow(page, f"{name} stop {step + 1}")
                    page.screenshot(path=str(out / f"{name}-stop{step + 1}-{width}.png"))
                forbidden("\n".join(panel_text), f"{name} Directions")

                # open from stop 5, copy, compare with the bundle
                page.locator("button[aria-controls='stop-4']").click()
                page.locator("#stop-4").get_by_role("button", name=re.compile("brief")).click()
                dialog = page.get_by_role("dialog")
                dialog.wait_for()
                assert "brief=1" in page.url
                assert page.evaluate("(() => { const d = document.querySelector('[data-family-brief]'); return d.scrollWidth <= d.clientWidth; })()"), f"{name} brief overflows"
                no_overflow(page, f"{name} brief")
                page.screenshot(path=str(out / f"{name}-brief-{width}.png"))
                dialog.get_by_role("button", name="Copy text").click()
                page.get_by_role("button", name="Copied").wait_for()
                copied = page.evaluate("navigator.clipboard.readText()")
                checked = check_text(copied, c)
                shown = dialog.inner_text()
                for o in c.get("communities") or []:
                    if o["kind"] in ("patient_organization", "research_program"):
                        assert o["homepage"] in shown
                for a in c.get("assets") or []:
                    assert a["url"] in shown and (not a["restriction"] or a["restriction"] in shown)
                if width == 1440:
                    (out / f"{name}-brief.txt").write_text(copied, encoding="utf-8")

                # print mode hides the map and app, shows the brief
                page.emulate_media(media="print")
                assert page.evaluate("getComputedStyle(document.getElementById('root')).display") == "none"
                assert dialog.is_visible()
                if width == 1440 and name == "stxbp1":
                    page.pdf(path=str(out / f"{name}-brief.pdf"), format="A4")
                page.emulate_media(media="screen")

                # Back button in the brief returns to Directions; browser Back too; Escape too
                dialog.get_by_role("button", name="Close the brief").click()
                dialog.wait_for(state="detached")
                assert "brief=" not in page.url, page.url
                page.get_by_role("button", name="Question brief", exact=True).click()
                dialog.wait_for()
                page.go_back()
                dialog.wait_for(state="detached")
                page.get_by_role("button", name="Question brief", exact=True).click()
                dialog.wait_for()
                page.keyboard.press("Escape")
                dialog.wait_for(state="detached")

                # a shared link: other parameters kept when closing
                page.goto(f"{base}/c/{cid}?from=shared&brief=1", wait_until="networkidle")
                dialog.wait_for()
                dialog.get_by_role("button", name="Close the brief").click()
                dialog.wait_for(state="detached")
                assert "from=shared" in page.url and "brief=" not in page.url, page.url
                print(json.dumps({"width": width, "condition": name, "stops": "pass", "brief": "pass", "listings_checked": checked}))
            assert not errors, errors
            context.close()
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
