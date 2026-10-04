"""Record a silent, real-site walkthrough draft; no model calls or submissions.

python tools/record_demo.py [--base URL] [--output DIRECTORY]
The output is a review/editing aid, not a completed narrated submission video.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright


def verify_recording(browser, output):
    """Decode the saved file in Chromium and sample its middle and final scene."""
    preview = output / "preview.html"
    preview.write_text('<!doctype html><title>Silent atlas walkthrough draft</title><video controls style="width:100%" src="atlas-walkthrough-silent.webm"></video>', encoding="utf-8")
    page = browser.new_page(viewport={"width": 1440, "height": 920})
    page.goto(preview.resolve().as_uri())
    page.wait_for_function("document.querySelector('video').readyState >= 2")
    metadata = page.locator("video").evaluate("v => ({seconds:v.duration,width:v.videoWidth,height:v.videoHeight})")
    assert metadata["seconds"] > 40 and metadata["width"] == 1440 and metadata["height"] == 900
    for name, seconds in [("middle", metadata["seconds"]/2), ("ending", metadata["seconds"]-2)]:
        page.locator("video").evaluate("(v,t) => new Promise(resolve => {v.addEventListener('seeked', resolve, {once:true});v.currentTime=t;})", seconds)
        page.screenshot(path=str(output / f"playback-{name}.png"))
    page.close()
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="https://salmon-island-04aa8f603.1.azurestaticapps.net")
    parser.add_argument("--output", type=Path, default=Path("data/build/demo") / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    scenes, errors = [], []
    started = time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900},
                                      record_video_dir=str(args.output / "raw"),
                                      record_video_size={"width": 1440, "height": 900},
                                      permissions=["clipboard-read", "clipboard-write"])
        page = context.new_page()
        video = page.video
        page.on("pageerror", lambda e: errors.append(str(e)))

        def hold(name, seconds, locator=None):
            if locator is not None:
                locator.scroll_into_view_if_needed()
            page.mouse.move(1400, 870)
            page.wait_for_timeout(300)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(args.output / f"{len(scenes)+1:02}-{name}.png"))
            scenes.append({"scene": name, "elapsed_seconds": round(time.monotonic()-started, 1), "url": page.url})
            page.wait_for_timeout(seconds * 1000)

        page.goto(args.base, wait_until="networkidle")
        page.get_by_role("link", name="SNAP25", exact=True).wait_for()
        hold("atlas", 3)
        page.get_by_role("link", name="SNAP25", exact=True).click()
        page.locator("#stop-0").wait_for()
        hold("diagnosis", 4, page.locator("#stop-0"))
        page.locator("button[aria-controls='stop-1']").click()
        assert "SNAP25 Foundation" in page.locator("#stop-1").inner_text()
        hold("community", 5, page.locator("#stop-1"))
        page.locator("button[aria-controls='stop-2']").click()
        hold("biological-leads", 5, page.locator("#stop-2"))
        page.locator("button[aria-controls='stop-4']").click()
        card = page.locator("[data-research-bridge]").first
        assert "STXBP1" in card.inner_text()
        hold("shared-registry-question", 7, card.locator("h4"))
        card.locator("summary").click()
        assert card.get_by_text("Evidence ID:", exact=False).count() == 2
        hold("source-and-restrictions", 6, card.locator("details"))
        card.get_by_role("button", name="Copy question + sources", exact=True).click()
        card.get_by_role("button", name="Question copied", exact=True).wait_for()
        copied = page.evaluate("navigator.clipboard.readText()")
        assert "NCT01238250" in copied and "STXBP1" in copied
        hold("copy-with-evidence", 3, card.get_by_role("button", name="Question copied", exact=True))
        page.get_by_role("button", name="Question brief", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.wait_for()
        hold("shareable-brief", 5, dialog.locator("h1"))
        page.keyboard.press("Escape")
        page.goto(args.base + "/c/MONDO:0012812", wait_until="networkidle")
        page.locator("button[aria-controls='stop-5']").click()
        history = page.get_by_role("region", name="Recent evidence checks")
        # The real contribution-cycle example should be among the visible checks.
        listing = history.locator("article").filter(has_text="Natural History").first
        listing.locator("summary").click()
        assert "Source checks passed" in listing.inner_text()
        hold("real-review-history", 7, listing)
        assert not errors, errors
        context.close()
        video.save_as(str(args.output / "atlas-walkthrough-silent.webm"))
        metadata = verify_recording(browser, args.output)
        browser.close()
    receipt = {"base": args.base, "recorded_at": datetime.now(timezone.utc).isoformat(),
               "status": "silent walkthrough draft; not narrated or submitted", "scenes": scenes,
               "page_errors": errors, "video": "atlas-walkthrough-silent.webm", "decoded_video": metadata}
    (args.output / "recording.json").write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "scenes": len(scenes), "page_errors": errors}))


if __name__ == "__main__":
    main()
