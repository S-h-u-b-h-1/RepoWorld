"""Offline browser acceptance for dense code city, labels and navigation.

Uses a synthetic 72-module graph. No GitHub, BharatCode, or Render calls.
Captures screenshots for human review; assertions guard browser regressions.
"""
from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"evidence"/"browser-qa"
KINDS=["core","frontend","api","service","library","database",
       "security","infra","test","docs"]


def fixture_graph():
    nodes=[]
    for i in range(72):
        kind=KINDS[i%len(KINDS)]
        name=f"{kind.title()} module {i:02d}"
        path=f"{kind}/module_{i:02d}"
        nodes.append({"id":path,"path":path,"kind":kind,"name":name,
            "fileCount":1+(i*41)%250,"description":"Synthetic QA fixture only",
            "fileIndex":[path+"/module.py"],"files":[path+"/module.py"],
            "symbols":[],"sampled":False})
    edges=[{"source":nodes[i]["id"],"target":nodes[i+1]["id"],"type":"import"}
           for i in range(0,len(nodes)-1,5)]
    return {"name":"Synthetic QA city — 72 modules","owner":"example",
        "url":"https://github.com/pallets/flask","branch":"HEAD",
        "source":"github","language":"Python","stars":None,
        "description":"Fictional browser QA fixture, not a live repository import.",
        "nodes":nodes,"edges":edges,
        "stats":{"modules":72,"files":2000,"dependencies":len(edges),
                 "inspectedSources":0,"partial":False},"warnings":["Synthetic fixture; no source inspected."]}


async def verify(browser,width,height):
    graph=fixture_graph()
    page=await browser.new_page(viewport={"width":width,"height":height},device_scale_factor=1)
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)))
    html=(ROOT/"app/static/index.html").read_text()
    for tag in ('<link rel="stylesheet" href="/static/styles.css">',
                '<script defer src="/static/world.js"></script>',
                '<script defer src="/static/browser-radar.js"></script>',
                '<script defer src="/static/app.js"></script>'):
        html=html.replace(tag,"")
    await page.set_content(html,wait_until="domcontentloaded")
    css=(ROOT/"app/static/styles.css").read_text()
    background=(ROOT/"app/static/city-concept.png").read_bytes()
    css=css.replace("url('/static/city-concept.png')",
        "url('data:image/png;base64,"+base64.b64encode(background).decode()+"')")
    await page.add_style_tag(content=css)
    issue={"number":25,"title":"Synthetic API crash report","state":"open",
           "url":"https://github.com/pallets/flask/issues/25","body":"Synthetic test report",
           "snippet":"Synthetic test report","labels":["bug"],"commentsCount":0,
           "matches":[{"nodeId":"api/module_02","confidence":"suggested",
                       "path":"api/module_02/module.py","evidence":"Fixture-only hint"}]}
    issue_data={"issues":[issue],"byNode":{"api/module_02":{"suggested":[25],"referenced":[]}},
                "total":1,"placed":1,"unplaced":0,"partial":False,
                "scope":"Synthetic QA issue, not observed GitHub data."}
    session={"authenticated":True,"guest":True,"csrf":"fixture-only",
             "repositories":[{"id":"fixture","name":graph["name"],
                              "owner":"example","fullName":"example/synthetic-fixture"}],
             "activeRepo":"fixture","aiConfigured":False}
    await page.evaluate("""(payload)=>{
      window.__CALLS__=[];
      window.__FIXTURE__=payload;
      window.fetch=async(input,options={})=>{
        const route=String(input), f=window.__FIXTURE__;
        window.__CALLS__.push(route);
        const data=route==='/api/session'?f.session:
          route==='/api/my-repos/fixture'?{id:'fixture',graph:f.graph}:
          route==='/api/my-repos/fixture/issues'?f.issues:
          route==='/api/tour'?{mode:'guided',steps:[]}: {error:'Unexpected fixture call'};
        return new Response(JSON.stringify(data),{
          status:data.error?404:200,headers:{'Content-Type':'application/json'}});
      };
    }""",{"graph":graph,"session":session,"issues":issue_data})
    await page.add_script_tag(content=(ROOT/"app/static/world.js").read_text())
    await page.evaluate("""(()=>{
      const Base=window.RepoWorldRenderer;
      window.RepoWorldRenderer=class extends Base {
        constructor(...args){super(...args);window.__TEST_SCENE__=this;}
      };
    })()""")
    await page.add_script_tag(content=(ROOT/"app/static/browser-radar.js").read_text())
    await page.add_script_tag(content=(ROOT/"app/static/app.js").read_text())
    await page.evaluate("document.dispatchEvent(new Event('DOMContentLoaded'))")
    await page.wait_for_function("""() => window.__TEST_SCENE__?.hitAreas.length===72 &&
        !document.getElementById('canvasStage').hidden""",timeout=15000)
    await page.wait_for_timeout(750)
    assert not await page.evaluate("document.documentElement.scrollWidth>innerWidth"),"Horizontal overflow"
    metrics=await page.evaluate("""() => {
      const scene=window.__TEST_SCENE__;
      // Tooltip <strong> is created on hover; measure its CSS without faking a hover.
      const tooltip=document.getElementById('sceneTooltip');
      const heading=document.createElement('strong');
      tooltip.append(heading);
      const tooltipFont=parseFloat(getComputedStyle(heading).fontSize);
      heading.remove();
      const overlap=scene.districts.some((d,i)=>scene.districts.some((e,j)=>i<j &&
        Math.abs(d.center.x-e.center.x)<d.halfWidth+e.halfWidth+5 &&
        Math.abs(d.center.z-e.center.z)<d.halfDepth+e.halfDepth+5));
      return {moduleCount:scene.nodes.length,districtCount:scene.districts.length,
        overlap,overviewDistance:scene.overviewDistance,
        inspectorFont:parseFloat(getComputedStyle(document.querySelector('.inspector-description')).fontSize),
        sceneFont:tooltipFont};
    }""")
    assert metrics["moduleCount"]==72 and metrics["districtCount"]>=6,metrics
    assert not metrics["overlap"],metrics
    assert metrics["inspectorFont"]>=14 and metrics["sceneFont"]>=14,metrics
    assert 110<=metrics["overviewDistance"]<=850,metrics
    await page.screenshot(path=str(OUT/f"city-{width}.png"),full_page=True)

    # Existing transient controls must be usable at both sizes.
    await page.locator("#mapCommandTrigger").click()
    await page.locator("#showMapOptions").click()
    assert await page.locator("#mapTools").is_visible()
    assert await page.locator("#districtJump option").count()>=7
    await page.screenshot(path=str(OUT/f"map-controls-{width}.png"),full_page=True)
    await page.locator("#nextBuilding").click()
    assert await page.locator("#inspector").is_visible()
    original=await page.locator("#inspectorName").inner_text()
    await page.locator("#worldCanvas").focus()
    await page.keyboard.press("]")
    assert await page.locator("#inspectorName").inner_text()!=original
    await page.screenshot(path=str(OUT/f"building-inspector-{width}.png"),full_page=True)
    await page.locator("#closeInspector").click()

    # Local issue search cannot call the provider again.
    await page.locator("#mapCommandTrigger").click()
    await page.locator('[data-compass-tab="issues"]').click()
    count=await page.evaluate("window.__CALLS__.length")
    await page.locator("#issueFilterText").fill("Synthetic API")
    assert await page.locator("#issueList .issue-item").count()==1
    await page.locator("#issueFilterType").select_option("enhancement")
    assert await page.locator("#issueList .issue-item").count()==0
    assert await page.evaluate("window.__CALLS__.length")==count
    await page.screenshot(path=str(OUT/f"issue-filters-{width}.png"),full_page=True)
    assert not errors,errors
    assert not await page.evaluate("document.documentElement.scrollWidth>innerWidth")
    print(f"PASS {width}x{height}: {metrics}; browser errors={errors}")
    await page.close()


async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
        for width,height in [(1440,900),(390,844)]:
            await verify(browser,width,height)
        await browser.close()


if __name__=="__main__":
    asyncio.run(main())
