"""Check live preference changes, static selection rings and usable map controls.

python tools/check_reduced_motion.py http://localhost:4173
"""
import sys
from playwright.sync_api import sync_playwright


def rendered(page):
    # Camera, Sigma render and React label placement use separate frames.
    # Software WebGL on CI can take longer than a fixed 120 ms to draw them.
    page.evaluate("""() => new Promise(resolve => {
        let frames = 0;
        function next() { if (++frames === 4) resolve(); else requestAnimationFrame(next); }
        requestAnimationFrame(next);
    })""")


def main(base):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in (1440, 390):
            page = browser.new_page(viewport={"width": width, "height": 900}, reduced_motion="no-preference")
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base + "/c/MONDO:0012812", wait_until="networkidle")
            canvas = page.locator("canvas[aria-label^='Interactive globe']")
            canvas.wait_for()
            # Change preference after mount; resetting the rotated globe must settle.
            page.emulate_media(reduced_motion="reduce")
            canvas.focus()
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(100)
            page.get_by_role("button", name="Reset globe view", exact=True).click()
            page.wait_for_timeout(120)
            first = canvas.evaluate("el => el.toDataURL()")
            page.wait_for_timeout(200)
            assert canvas.evaluate("el => el.toDataURL()") == first, "Reduced-motion globe keeps moving"
            page.get_by_role("button", name="Flat map", exact=True).click()
            ring = page.locator("[data-focus-ring]")
            ring.wait_for(state="attached")
            assert ring.evaluate("el => getComputedStyle(el).animationName") == "none"
            rendered(page)
            positions = "() => [...document.querySelectorAll('button[aria-label^=\"Directions stop\"]')].map(el => [el.style.left, el.style.top])"
            before = page.evaluate(positions)
            assert before, "Flat map has no route markers"
            selected = ring.bounding_box()
            assert selected and 0 < selected["x"] < width and 0 < selected["y"] < 900, "Selection is outside the viewport"
            page.get_by_role("button", name="Zoom in", exact=True).click()
            rendered(page)
            first = page.evaluate(positions)
            assert first != before, "Zoom did not change the route placement"
            page.wait_for_timeout(200)
            second = page.evaluate(positions)
            assert first == second, f"Reduced-motion flat camera keeps moving: {first} -> {second}"
            page.get_by_role("button", name="Zoom out", exact=True).click()
            # Restore the preference without reloading; CSS and listener update.
            page.emulate_media(reduced_motion="no-preference")
            page.wait_for_function("getComputedStyle(document.querySelector('[data-focus-ring]')).animationName !== 'none'")
            page.emulate_media(reduced_motion="reduce")
            page.wait_for_function("getComputedStyle(document.querySelector('[data-focus-ring]')).animationName === 'none'")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            print(f"PASS {width}px: live motion preference, globe settles, flat ring static, zoom usable", flush=True)
            page.close()
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1])
