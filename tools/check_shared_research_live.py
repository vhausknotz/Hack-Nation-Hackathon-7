"""Verify the deployed build and copied research bridge against local bundles."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from check_family_brief import bundle, check_text, check_history, check_shared_question, no_overflow

BASE = "https://salmon-island-04aa8f603.1.azurestaticapps.net"
ROOT = Path(__file__).resolve().parents[1]


def main():
    expected = re.search(r'/assets/index-[^" ]+\.js', (ROOT / "app/dist/index.html").read_text()).group()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for cid, width in [("MONDO:0012812", 1440), ("MONDO:0014590", 390), ("MONDO:0012960", 390)]:
            context = browser.new_context(viewport={"width": width, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{BASE}/c/{cid}?brief=1", wait_until="networkidle")
            assert expected in page.content(), "Live website has a different build"
            dialog = page.get_by_role("dialog")
            dialog.wait_for()
            assert dialog.get_by_text("Shared research: questions for patient-group organizers", exact=True).is_visible()
            dialog.get_by_role("button", name="Copy text", exact=True).click()
            page.get_by_role("button", name="Copied", exact=True).wait_for()
            check_text(page.evaluate("navigator.clipboard.readText()"), bundle(cid))
            no_overflow(page, "live shared-research brief")
            page.keyboard.press("Escape")
            dialog.wait_for(state="detached")
            page.locator("button[aria-controls='stop-4']").click()
            assert page.get_by_role("region", name="Shared research for patient-group organizers").is_visible()
            check_shared_question(page, bundle(cid))
            page.locator("button[aria-controls='stop-5']").click()
            check_history(page, bundle(cid))
            assert not errors, errors
            print(f"PASS {cid} at {width}px, deployed {expected}", flush=True)
            context.close()
        browser.close()


if __name__ == "__main__":
    main()
