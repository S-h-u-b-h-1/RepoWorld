"""Record real RepoWorld production footage for the hackathon demo.

One public import, no private repositories, no AI/provider calls, no secrets logged.
All footage uses the live deployed website; synthetic scenes are forbidden.
"""
import asyncio
import json
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

SITE = "https://repoworld-3b9e.onrender.com"
REPO = "zulip/zulip-terminal"
ROOT = Path("evidence/public-demo")
ROOT.mkdir(parents=True, exist_ok=True)
MARKERS = []
START = None

def mark(name, detail=""):
    elapsed = round(time.monotonic() - START, 2) if START is not None else 0
    MARKERS.append({"name": name, "seconds": elapsed, "detail": detail})
    print(f"SHOT {name} at {elapsed:.2f}s {detail}", flush=True)

async def pause(seconds):
    await asyncio.sleep(seconds)

async def screenshot(page, slug):
    await page.screenshot(path=str(ROOT / (slug + ".png")), animations="disabled")

async def warm_backend():
    print("Checking public deployment readiness; no GitHub import yet", flush=True)
    timeout = httpx.Timeout(38, connect=12)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(5):
            try:
                r = await client.get(SITE + "/api/ready")
                if r.status_code == 200 and r.json().get("ready") is True:
                    print("PASS backend ready", flush=True)
                    return
            except (httpx.RequestError, ValueError):
                pass
            await asyncio.sleep(5)
    raise RuntimeError("Public backend unavailable: no synthetic substitute will be recorded")

async def prep_city(browser):
    context = await browser.new_context(viewport={"width":1920,"height":1080}, device_scale_factor=1,
                                        reduced_motion="reduce")
    page = await context.new_page()
    await page.goto(SITE, wait_until="domcontentloaded", timeout=75000)
    await page.locator("#workspace").wait_for(state="visible", timeout=60000)
    await page.locator("#emptyState").wait_for(state="visible", timeout=25000)
    await page.locator("#emptyAddRepo").click()
    await page.locator("#importInput").fill(REPO)
    await page.locator("#importButton").click()
    await page.locator("#canvasStage").wait_for(state="visible", timeout=110000)
    await page.locator("#mapCommandTrigger").wait_for(state="visible", timeout=12000)
    await pause(2)
    await context.storage_state(path=str(ROOT/"guest-state.json"))
    await page.close()
    await context.close()
    print("PASS real public city imported; saved guest-only cookies in ephemeral runner", flush=True)

async def click(page, selector, **kwargs):
    try:
        await page.locator(selector).first.click(timeout=7000, **kwargs)
        return True
    except Exception as exc:
        print("Optional scene could not click",selector,type(exc).__name__,flush=True)
        return False

async def capture(browser):
    global START
    context=await browser.new_context(
        viewport={"width":1920,"height":1080},device_scale_factor=1,
        record_video_dir=str(ROOT),record_video_size={"width":1920,"height":1080},
        storage_state=str(ROOT/"guest-state.json"),reduced_motion="reduce",
        color_scheme="dark")
    page=await context.new_page()
    await page.goto(SITE,wait_until="domcontentloaded",timeout=75000)
    await page.locator("#canvasStage").wait_for(state="visible",timeout=75000)
    await page.locator("#mapCommandTrigger").wait_for(state="visible",timeout=12000)
    await pause(1.5)
    START=time.monotonic()
    video=page.video

    # Sequence is intentionally calm, paced for a 95-105 second human voiceover.
    mark("city_overview","real public repository")
    await screenshot(page,"01-city")
    await page.mouse.move(1840,960)
    await pause(7)

    mark("city_orbit","slow, stable mouse gesture")
    canvas=page.locator("#worldCanvas")
    box=await canvas.bounding_box()
    if box:
        x=box["x"]+box["width"]*0.49
        y=box["y"]+box["height"]*0.53
        await page.mouse.move(x,y)
        await page.mouse.down()
        for t in range(28):
            await page.mouse.move(x+95*(t+1)/28,y+16*(t+1)/28)
            await asyncio.sleep(.035)
        await page.mouse.up()
    await page.mouse.move(1840,960)
    await pause(6)

    mark("city_controls","code districts and navigation")
    if await click(page,"#mapCommandTrigger"):
        await click(page,"#showMapOptions")
    await screenshot(page,"02-city-controls")
    await pause(5)

    mark("real_building","inspector, sampled imports and real paths")
    if await click(page,"#nextBuilding"):
        await page.locator("#inspector").wait_for(state="visible",timeout=8000)
    await screenshot(page,"03-real-building")
    await pause(9)
    await click(page,"#closeInspector")
    await pause(1.5)

    mark("find_code","actual repository path search")
    await click(page,"#mapCommandTrigger")
    await click(page,'[data-compass-tab="find"]')
    await page.locator("#searchInput").fill("model")
    await pause(2.2)
    await screenshot(page,"04-find-code")
    await pause(6)
    if await page.locator("#searchResults .search-result").count():
        await click(page,"#searchResults .search-result")
    await pause(3)
    await click(page,"#closeInspector")

    mark("issue_radar","live GitHub issue list")
    await click(page,"#mapCommandTrigger")
    await click(page,'[data-compass-tab="issues"]')
    await pause(1.5)
    await screenshot(page,"05-open-issues")
    await pause(8)

    mark("issue_investigation","reported issue; no bug reproduction claimed")
    if await page.locator("#issueList .issue-item .issue-title-button").count():
        await click(page,"#issueList .issue-item .issue-title-button")
        await pause(2.5)
        await screenshot(page,"06-issue-investigation")
        await pause(6)
        await click(page,"#closeIssueDrawer")
    else:
        print("WARN no issue items visible; will not invent one",flush=True)
        await pause(7)

    mark("assistant_console","no unverified AI generation portrayed")
    await click(page,"#mapCommandTrigger")
    await click(page,'[data-compass-tab="ask"]')
    await screenshot(page,"07-developer-assistant")
    await pause(8)

    mark("return_to_city","final live app shot")
    await click(page,"#closeSearch")
    await screenshot(page,"08-closing-city")
    await pause(8)
    await page.close()
    await video.save_as(str(ROOT/"real-product-footage.webm"))
    await context.close()
    (ROOT/"shot-markers.json").write_text(json.dumps(MARKERS,indent=2))
    print("PASS captured authentic deployment footage",flush=True)

async def main():
    await warm_backend()
    async with async_playwright() as p:
        browser=await p.chromium.launch(channel="chrome",headless=True,args=["--no-sandbox"])
        await prep_city(browser)
        try:
            await capture(browser)
        finally:
            await browser.close()

if __name__=="__main__":
    asyncio.run(main())
