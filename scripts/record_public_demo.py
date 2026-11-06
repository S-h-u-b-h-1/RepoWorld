"""Capture high-resolution, authentic RepoWorld frames for editorial demo.

The recording is a visual proof-of-product, not an AI-generated simulation.
Uses one confirmed public repository import and no BharatCode generation.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time

import httpx
from playwright.async_api import async_playwright

SITE = "https://repoworld-3b9e.onrender.com"
REPOSITORY = "zulip/zulip-terminal"
OUT = Path("evidence/public-demo")
OUT.mkdir(parents=True, exist_ok=True)
SHOTS = []


async def check_ready() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(35, connect=10)) as client:
        for attempt in range(5):
            try:
                response = await client.get(SITE + "/api/ready")
                if response.status_code == 200 and response.json().get("ready") is True:
                    print("PASS real deployment ready", flush=True)
                    return
            except (httpx.RequestError, ValueError):
                pass
            await asyncio.sleep(5)
    raise RuntimeError("Production website unavailable; cannot substitute synthetic footage")


async def optional_click(page, selector: str):
    try:
        await page.locator(selector).first.click(timeout=10000)
        return True
    except Exception as exc:
        print("Optional action unavailable:", selector, type(exc).__name__, flush=True)
        return False


async def photo(page, slug: str, caption: str):
    # deviceScaleFactor=2 gives 3200x1800 source pixels for a 1600x900 CSS viewport.
    filename = f"{len(SHOTS)+1:02d}-{slug}.png"
    await page.screenshot(path=str(OUT / filename), animations="disabled")
    SHOTS.append({"file": filename, "scene": slug, "caption": caption})
    print(f"FRAME {filename}: {caption}", flush=True)


async def main():
    await check_ready()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context(
            viewport={"width": 1600, "height": 900},
            device_scale_factor=2,
            reduced_motion="reduce",
            color_scheme="dark",
        )
        page = await context.new_page()
        await page.goto(SITE, wait_until="domcontentloaded", timeout=90000)
        await page.locator("#workspace").wait_for(state="visible", timeout=80000)
        if await page.locator("#emptyState").is_visible():
            await optional_click(page, "#emptyAddRepo")
            await page.locator("#importInput").fill(REPOSITORY)
            await optional_click(page, "#importButton")
        await page.locator("#canvasStage").wait_for(state="visible", timeout=110000)
        await page.locator("#mapCommandTrigger").wait_for(state="visible", timeout=14000)
        await asyncio.sleep(2)

        # Only genuine content observed in the current public workspace.
        await photo(page, "city-overview", "Actual imported public GitHub city")
        box = await page.locator("#worldCanvas").bounding_box()
        if box:
            await page.mouse.move(box["x"] + box["width"]*.48, box["y"] + box["height"]*.53)
            await page.mouse.wheel(0, -400)
            await asyncio.sleep(1.3)
        await photo(page, "city-focused", "Larger steady 3D city view")

        await optional_click(page, "#mapCommandTrigger")
        await optional_click(page, "#showMapOptions")
        await photo(page, "map-controls", "Observed city navigation and layer tools")

        await optional_click(page, "#nextBuilding")
        await asyncio.sleep(.45)
        if await page.locator("#inspector").is_visible():
            await photo(page, "module-inspector", "Real indexed building and source paths")
            await page.locator("#inspector").evaluate("el => el.scrollTop = Math.min(el.scrollHeight/2, 400)")
            await asyncio.sleep(.2)
            await photo(page, "module-evidence", "Sampled files and static imports")
            await optional_click(page, "#closeInspector")

        await optional_click(page, "#mapCommandTrigger")
        await optional_click(page, '[data-compass-tab="find"]')
        await page.locator("#searchInput").fill("model")
        await asyncio.sleep(1)
        await photo(page, "find-code", "Real code search for matching path names")

        await optional_click(page, '[data-compass-tab="issues"]')
        await asyncio.sleep(1.5)
        await photo(page, "issue-radar", "Live issue feed with source-qualified locations")
        if await page.locator("#issueList .issue-item .issue-title-button").count():
            await optional_click(page, "#issueList .issue-item .issue-title-button")
            await asyncio.sleep(1.1)
            await photo(page, "issue-investigation", "Real public issue and investigation view")
            await optional_click(page, "#closeIssueDrawer")

        await optional_click(page, "#mapCommandTrigger")
        await optional_click(page, '[data-compass-tab="ask"]')
        await photo(page, "developer-assistant", "Source-scoped assistant interface; no inference claimed")
        await optional_click(page, "#closeSearch")
        await photo(page, "closing-city", "Public city after console is closed")

        # Double-check we have actual 2x screenshots, not a reduced-size browser recording.
        import struct
        for shot in SHOTS:
            with (OUT / shot["file"]).open("rb") as image_file:
                header = image_file.read(24)
            width, height = struct.unpack(">II", header[16:24])
            if (width, height) != (3200, 1800):
                raise RuntimeError(f"Capture unexpectedly changed size: {width}x{height}")
        (OUT / "shot-index.json").write_text(json.dumps({
            "source": SITE, "repository": REPOSITORY, "synthetic": False,
            "resolution": [3200, 1800], "shots": SHOTS,
            "note": "Images are of the real public product. No AI response was fabricated."
        }, indent=2), encoding="utf-8")
        print("PASS high-density production screenshots:", len(SHOTS), flush=True)
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
