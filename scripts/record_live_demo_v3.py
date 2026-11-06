"""Record an authentic, continuous 1080p RepoWorld walkthrough directly from a live browser.

The browser window is screen-captured at 30 fps via Xvfb+FFmpeg with Chrome
toolbar cropped at capture time. Real GitHub repository import, no AI calls.
"""
from __future__ import annotations
import asyncio
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

URL = "https://repoworld-3b9e.onrender.com"
REPO = "zulip/zulip-terminal"
OUT = Path("evidence/demo-live")
OUT.mkdir(parents=True, exist_ok=True)
EVENTS = []
T0 = None

def stamp(scene, description):
    t = max(0, time.monotonic()-T0) if T0 else 0
    EVENTS.append({"scene":scene,"start_s":round(t,3),"description":description})
    print(f"SHOT {scene} time={t:.2f}s: {description}",flush=True)

async def warm():
    async with httpx.AsyncClient(timeout=httpx.Timeout(38,connect=12),follow_redirects=False) as client:
        for _ in range(6):
            try:
                r=await client.get(URL+"/api/ready")
                if r.status_code==200 and r.json().get("ready") is True:
                    print("PASS production backend ready",flush=True);return
            except (httpx.RequestError, ValueError):pass
            await asyncio.sleep(6)
    raise RuntimeError("Public production unavailable; never replace real footage with mock content")

async def tap(page, selector, required=False):
    try:
        await page.locator(selector).first.click(timeout=9500)
        return True
    except Exception as exc:
        print(f"{'FAIL' if required else 'WARN'} click {selector} {type(exc).__name__}",flush=True)
        if required:raise
        return False

async def take(page, name):
    await page.screenshot(path=str(OUT/f"live-{name}.png"),animations="disabled",timeout=20000)

async def scripted_scene(name, seconds, page, action=None, detail=""):
    stamp(name,detail)
    start=time.monotonic()
    if action:await action()
    await asyncio.sleep(max(0, seconds-(time.monotonic()-start)))
    await page.mouse.move(1860,1030)

async def main():
    global T0
    if not shutil.which("ffmpeg"):raise RuntimeError("ffmpeg must be installed on recording runner")
    await warm()
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(
            channel="chrome",headless=False,
            args=["--no-sandbox","--disable-dev-shm-usage","--window-size=1920,1170","--window-position=0,0",
                  "--force-device-scale-factor=1","--disable-infobars","--disable-notifications"])
        ctx=await browser.new_context(viewport={"width":1920,"height":1080},device_scale_factor=1,
            reduced_motion="reduce",color_scheme="dark",accept_downloads=False)
        page=await ctx.new_page()
        await page.goto(URL,wait_until="domcontentloaded",timeout=90000)
        await page.locator("#workspace").wait_for(state="visible",timeout=90000)
        await page.wait_for_function("""() => {
           const e=document.querySelector('#emptyState'),c=document.querySelector('#canvasStage');
           return (e&&!e.hidden)||(c&&!c.hidden);
        }""",timeout=45000)
        if await page.locator("#emptyState").is_visible():
            await tap(page,"#emptyAddRepo",required=True)
            await page.locator("#importInput").fill(REPO)
            await tap(page,"#importButton",required=True)
        await page.locator("#canvasStage").wait_for(state="visible",timeout=120000)
        await page.locator("#mapCommandTrigger").wait_for(state="visible",timeout=15000)
        await asyncio.sleep(2)
        title=await page.locator("#activeRepoTitle").inner_text()
        print("PASS imported real city",title,flush=True)
        if "zulip" not in title.lower():
            raise RuntimeError("Could not confirm real zulip-terminal city, aborting recording")
        await take(page,"opening")
        # Xvfb screen is 1920x1170; top 90px is browser chrome. Source crop is
        # exactly the 1920x1080 real application viewport, not an upscale.
        display=os.environ.get("DISPLAY",":99")
        source=display+".0+0,90"
        output=OUT/"RepoWorld_Live_RealScreen_30fps.mp4"
        log=open(OUT/"capture-encoder.log","w")
        cmd=["ffmpeg","-hide_banner","-nostats","-loglevel","warning","-y",
             "-thread_queue_size","512","-f","x11grab","-draw_mouse","0",
             "-framerate","30","-video_size","1920x1080","-i",source,
             "-an","-c:v","libx264","-preset","ultrafast","-crf","17",
             "-pix_fmt","yuv420p","-movflags","+faststart",str(output)]
        process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log)
        await asyncio.sleep(1)
        if process.poll() is not None:
            raise RuntimeError("FFmpeg could not start; check capture-encoder.log")
        T0=time.monotonic()

        async def orbit():
            canvas=await page.locator("#worldCanvas").bounding_box()
            if canvas:
                x=canvas["x"]+canvas["width"]*.52;y=canvas["y"]+canvas["height"]*.54
                await page.mouse.move(x,y)
                await page.mouse.down()
                for frame in range(28):
                    t=(frame+1)/28;ease=t*t*(3-2*t)
                    await page.mouse.move(x+65*ease,y+13*ease)
                    await asyncio.sleep(.038)
                await page.mouse.up()
            await page.mouse.move(1860,1030)

        async def zoom():
            await page.mouse.move(1860,1030)
            await page.mouse.wheel(0,-120)
            await asyncio.sleep(.75)
            await page.mouse.wheel(0,-120)

        async def city_links():
            await tap(page,"#mapCommandTrigger",required=True)
            await tap(page,"#showMapOptions",required=True)
            await tap(page,'[data-layer="dependencies"]')
            await take(page,"connections")

        async def building():
            if await page.locator("#mapTools").is_visible():
                await tap(page,'[data-layer="structure"]')
                await tap(page,"#nextBuilding",required=True)
            else:
                await tap(page,"#mapCommandTrigger")
                await tap(page,"#showMapOptions")
                await tap(page,"#nextBuilding",required=True)
            await page.locator("#inspector").wait_for(state="visible",timeout=8000)
            await take(page,"inspector")
            await page.mouse.move(1860,1030)

        async def evidence():
            if await page.locator("#inspector").is_visible():
                await page.locator("#inspector").evaluate("el=>el.scrollTo({top:Math.min(360,el.scrollHeight/2),behavior:'smooth'})")
                await asyncio.sleep(.75)
            await take(page,"source")

        async def find_code():
            await tap(page,"#closeInspector")
            if await page.locator("#mapTools").is_visible():
                await tap(page,"#findButton",required=True)
            else:
                await tap(page,"#mapCommandTrigger",required=True)
                await tap(page,'[data-compass-tab="find"]',required=True)
            await tap(page,'[data-compass-tab="find"]',required=True)
            await page.locator("#searchInput").fill("")
            await page.locator("#searchInput").press_sequentially("model",delay=90)
            await asyncio.sleep(1.5)
            await take(page,"find-code")

        async def issue_radar():
            if not await page.locator("#searchDialog").is_visible():
                await tap(page,"#mapCommandTrigger",required=True)
            await tap(page,'[data-compass-tab="issues"]',required=True)
            await asyncio.sleep(1.5)
            await take(page,"issues")

        async def inspect_issue():
            titles=page.locator("#issueList .issue-item .issue-title-button")
            if await titles.count():
                await tap(page,"#issueList .issue-item .issue-title-button",required=True)
                await page.locator("#issueDrawer").wait_for(state="visible",timeout=10000)
                await asyncio.sleep(.75)
                if await page.locator("#issueOriginalReport").count():
                    await tap(page,"#issueOriginalReport summary")
                await take(page,"issue-details")
            else:
                print("WARN no live issue items available; hold real issue UI without fabricating content",flush=True)

        async def assistant():
            await tap(page,"#closeIssueDrawer")
            await tap(page,"#mapCommandTrigger",required=True)
            await tap(page,'[data-compass-tab="ask"]',required=True)
            await page.locator("#assistantQuestion").fill("Where should I start exploring this repository?")
            await take(page,"assistant")
            # We DO NOT click Send, because the live BharatCode inference gate has not passed.

        async def portability():
            await tap(page,"#closeSearch")
            await tap(page,"#repoMenuButton")
            await take(page,"portability")

        async def closing():
            await tap(page,"#repoMenuButton")
            await tap(page,"#mapCommandTrigger")
            await tap(page,"#showMapOptions")
            await tap(page,"#resetCamera")
            await take(page,"closing")

        try:
            await scripted_scene("opening",6,page,None,"True RepoWorld city and creator introduction")
            await scripted_scene("problem",11,page,orbit,"Live mouse-driven orbit across the actual city")
            await scripted_scene("city-overview",13,page,zoom,"Live building overview and stable zoom")
            await scripted_scene("links",12,page,city_links,"Real sampled static import links layer")
            await scripted_scene("module",12,page,building,"Click a real building and inspect its indexed code")
            await scripted_scene("source-evidence",9,page,evidence,"Scroll genuine source and module information")
            await scripted_scene("find-code",14,page,find_code,"Type a real path-search query")
            await scripted_scene("issues",13,page,issue_radar,"Live GitHub issues and placement qualifications")
            await scripted_scene("issue-details",14,page,inspect_issue,"Open actual issue without pretending verification")
            await scripted_scene("assistant",13,page,assistant,"Display source-scoped assistant without invoking a model")
            await scripted_scene("portability",8,page,portability,"Show real local backup and portable map options")
            await scripted_scene("closing",9,page,closing,"Return to a clean full-frame city")
        finally:
            duration=round(time.monotonic()-T0,3)
            try:
                process.stdin.write(b"q\n")
                process.stdin.flush()
                process.communicate(timeout=80)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
            log.close()
            (OUT/"capture-markers.json").write_text(json.dumps({
                "source":URL,"repository":REPO,"synthetic":False,
                "captured_realtime":True,"fps":30,"width":1920,"height":1080,
                "duration_s":duration,"encoder_returncode":process.returncode,"scenes":EVENTS
            },indent=2),encoding="utf8")
            await ctx.close()
            await browser.close()
        if process.returncode!=0 or output.stat().st_size<100000:
            raise RuntimeError("Live capture did not complete successfully")
        print("PASS live capture",output,"duration",duration,"bytes",output.stat().st_size,flush=True)

if __name__=="__main__":
    asyncio.run(main())
