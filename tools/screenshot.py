"""Take full-page screenshots of app routes for visual review.

Usage: python tools/screenshot.py <out_dir> <base_url> <path> [<path> ...] [--width 1440] [--search "SNAP"]
With --search, also types the query into the home page search box and captures the dropdown.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main(args: list[str]) -> None:
    width = int(args[args.index("--width") + 1]) if "--width" in args else 1440
    query = args[args.index("--search") + 1] if "--search" in args else None
    flags = {"--width", "--search"}
    positional = [a for i, a in enumerate(args) if a not in flags and (i == 0 or args[i - 1] not in flags)]
    out, base, paths = Path(positional[0]), positional[1].rstrip("/"), positional[2:]
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=1)
        errors: list[str] = []
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        for path in paths:
            page.goto(base + path, wait_until="networkidle")
            page.wait_for_timeout(400)
            name = path.strip("/").replace("/", "_").replace(":", "-") or "home"
            file = out / f"{name}_{width}.png"
            page.screenshot(path=str(file), full_page=True)
            print(f"{file}  ({page.title()})")
            overflow = page.evaluate("""() => {
                const vw = document.documentElement.clientWidth, out = [];
                for (const el of document.querySelectorAll('body *')) {
                    const r = el.getBoundingClientRect();
                    if (r.right > vw + 1 && r.width > 0) out.push(`${el.tagName.toLowerCase()}.${(el.className?.baseVal ?? el.className ?? '').toString().slice(0, 60)} right=${Math.round(r.right)}`);
                }
                return out.slice(0, 8);
            }""")
            for o in overflow:
                print("  overflow:", o)
        if query:
            page.goto(base + "/", wait_until="networkidle")
            page.get_by_role("combobox").fill(query)
            page.wait_for_timeout(1500)
            file = out / f"search_{query.replace(' ', '_')}_{width}.png"
            page.screenshot(path=str(file), full_page=False)
            print(file)
        for e in errors:
            print(e)
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
