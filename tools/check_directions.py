"""Exercise the family journey on a local preview; save desktop and phone screenshots.

python tools/check_directions.py http://localhost:4173 data/build/directions-qa
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main(base: str, output: str):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (1440, 390):
            page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/c/MONDO:0012812", wait_until="networkidle")
            page.locator("button[aria-controls='stop-0']").wait_for()
            page.wait_for_timeout(1000)
            for step in (0, 1, 2, 3, 4, 5):
                button = page.locator(f"button[aria-controls='stop-{step}']")
                button.click()
                panel = page.locator(f"#stop-{step}")
                assert panel.is_visible()
                if step == 1:
                    assert "STXBP1 Foundation" in panel.inner_text()
                if step == 3:
                    assert "Check study and eligibility" in panel.inner_text()
                    panel.locator("details").first.locator("summary").click()
                    assert "reviewer" in panel.inner_text()
                if step == 4:
                    assert "Prepare one question" in panel.inner_text()
                page.screenshot(path=str(out / f"stxbp1-step-{step + 1}-{width}.png"))
            page.get_by_role("button", name="Flat map", exact=True).click()
            page.wait_for_timeout(1200)
            page.screenshot(path=str(out / f"flat-map-{width}.png"))
            page.get_by_role("button", name="Globe", exact=True).click()
            page.wait_for_timeout(1000)
            page.get_by_role("button", name="Zoom in", exact=True).click()
            page.get_by_role("button", name="Zoom out", exact=True).click()
            canvas = page.locator("canvas[aria-label^='Interactive globe']")
            box = canvas.bounding_box()
            x, y = box["x"] + box["width"] * .5, box["y"] + box["height"] * .5
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 60, y + 20, steps=8)
            page.mouse.up()
            canvas.focus()
            page.keyboard.press("ArrowRight")
            page.keyboard.press("+")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert not errors, errors
            print(json.dumps({"width": width, "six_stops": "pass", "globe_and_flat_controls": "pass", "page_errors": errors}))
            page.close()
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
