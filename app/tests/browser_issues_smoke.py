"""Offline Chromium regression for browser-direct GitHub Issue Radar.

No real GitHub, BharatCode or Render requests. Runs the real renderer and
controller with explicit mock provider responses.
"""
import asyncio
import base64
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from playwright.async_api import async_playwright
from app.demo import build_demo

OUT=ROOT/'evidence'/'browser-qa'

async def check(page,graph):
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    html=(ROOT/'app/static/index.html').read_text()
    for tag in ('<link rel="stylesheet" href="/static/styles.css">',
                '<script defer src="/static/world.js"></script>',
                '<script defer src="/static/browser-radar.js"></script>',
                '<script defer src="/static/investigation-notes.js"></script>',
                '<script defer src="/static/offline-city.js"></script>',
                '<script defer src="/static/app.js"></script>'):
        html=html.replace(tag,'')
    await page.set_content(html)
    css=(ROOT/'app/static/styles.css').read_text()
    img=base64.b64encode((ROOT/'app/static/city-concept.png').read_bytes()).decode()
    css=css.replace("url('/static/city-concept.png')","url('data:image/png;base64,"+img+"')")
    await page.add_style_tag(content=css)
    issue={'number':73,'title':'Fix apps/web/src/app.tsx startup',
           'state':'open','body':'apps/web/src/app.tsx has an error',
           'labels':[{'name':'bug'}],'comments':2}
    session={'authenticated':True,'guest':True,'csrf':'fixture',
             'repositories':[{'id':'demo','owner':'pallets','name':'flask','fullName':'pallets/flask'}],
             'activeRepo':'demo','aiConfigured':False}
    await page.evaluate('''({graph,session,issue})=>{
      window.__API_LOG__=[];
      window.fetch=async(url,opts={})=>{
        const key=String(url);window.__API_LOG__.push({url:key,credentials:opts.credentials});
        const direct=key.startsWith('https://api.github.com/repos/pallets/flask/issues?');
        const status=key==='/api/my-repos/demo/issues'?429:200;
        let response=key==='/api/session'?session:
           key==='/api/my-repos/demo'?{id:'demo',graph}:
           key==='/api/my-repos/demo/issues'?{error:'GitHub issue API rate limit reached.'}:
           key==='/api/my-repos/demo/source-lead'?{mode:'source-lead',
             issueVerified:false,assistantUsed:false,sourceFilesRead:1,sourceScope:'live-branch',
             sources:[{file:'apps/web/src/app.tsx',evidence:'excerpt',
               url:'https://github.com/pallets/flask/blob/HEAD/apps/web/src/app.tsx#L4-L9',
               matchKind:'path-hint',matchedSymbols:[],preview:'4: export function startApp(){}'}]}:
           direct?[issue,{number:74,title:'A pull request',state:'open',pull_request:{url:'x'}}]:
           key==='/api/tour'?{mode:'guided',steps:[]}:{error:'Unexpected '+key};
        return new Response(JSON.stringify(response),{status:response.error?status===429?429:404:200,
          headers:{'Content-Type':'application/json','Retry-After':'80'}});
      }
    }''',{'graph':graph,'session':session,'issue':issue})
    await page.add_script_tag(content=(ROOT/'app/static/world.js').read_text())
    await page.add_script_tag(content=(ROOT/'app/static/browser-radar.js').read_text())
    await page.add_script_tag(content=(ROOT/'app/static/investigation-notes.js').read_text())
    await page.add_script_tag(content=(ROOT/'app/static/offline-city.js').read_text())
    await page.add_script_tag(content=(ROOT/'app/static/app.js').read_text())
    await page.evaluate('document.dispatchEvent(new Event("DOMContentLoaded"))')
    await page.locator('#canvasStage').wait_for(state='visible')
    await page.wait_for_function("document.querySelector('#issueSummary')?.textContent?.includes('BROWSER GITHUB FEED')",timeout=10000)
    await page.locator('#mapCommandTrigger').click(timeout=5000)
    await page.locator('[data-compass-tab="issues"]').click(timeout=5000)
    await page.locator('#issueList .issue-item .issue-title-button').first.click(timeout=5000)
    await page.wait_for_function("document.querySelector('#issueAiHeading')?.textContent?.includes('UNVERIFIED')",timeout=5000)
    assert await page.locator('#issueGithubLink').get_attribute('href')=='https://github.com/pallets/flask/issues/73'
    log=await page.evaluate('window.__API_LOG__')
    assert len([x for x in log if x['url'].startswith('https://api.github.com/')])==1
    assert not any(x['url']=='/api/my-repos/demo/assistant' for x in log)
    assert not any(x['url']=='/api/my-repos/demo/source-lead' for x in log)
    await page.locator('#issueInspectSource').click()
    await page.wait_for_function("document.querySelector('#issueAiHeading')?.textContent?.includes('ISSUE UNVERIFIED')")
    assert 'No reported identifiers were confirmed' in await page.locator('.source-lead-summary').inner_text()
    assert 'Path/title search hint only' in await page.locator('.source-lead-meta').first.inner_text()
    assert await page.locator('.source-lead-card > a').first.get_attribute('href')==(
      'https://github.com/pallets/flask/blob/HEAD/apps/web/src/app.tsx#L4-L9')
    await page.evaluate("""() => Object.defineProperty(navigator,'clipboard',{
      configurable:true,value:{writeText:async text=>{window.__QA_NOTES__=text;}}
    })""")
    await page.locator('#issueCopyNotes').click()
    await page.wait_for_function("typeof window.__QA_NOTES__==='string'")
    notes=await page.evaluate('window.__QA_NOTES__')
    assert 'public source independently inspected; issue not verified' in notes,notes
    assert 'Separately fetched public source' in notes,notes
    assert 'search candidate only; no reported identifier confirmed' in notes,notes
    assert 'AI-generated suggestion' not in notes,notes
    log=await page.evaluate('window.__API_LOG__')
    assert len([x for x in log if x['url']=='/api/my-repos/demo/source-lead'])==1
    assert not any(x['url']=='/api/my-repos/demo/assistant' for x in log)
    assert not errors,errors
    assert not await page.evaluate('document.documentElement.scrollWidth>window.innerWidth')

async def main():
    graph=build_demo()
    graph.update({'name':'flask','owner':'pallets','source':'github',
                  'url':'https://github.com/pallets/flask','branch':'HEAD'})
    OUT.mkdir(exist_ok=True)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True,args=['--no-sandbox'])
        for w,h in [(1440,900),(390,844)]:
            page=await browser.new_page(viewport={'width':w,'height':h})
            await check(page,graph)
            await page.screenshot(path=str(OUT/f'issue-browser-fallback-{w}.png'))
            print(f'PASS browser fallback {w}x{h}: issue link, no server verification claims')
            await page.close()
        await browser.close()

if __name__=='__main__':asyncio.run(main())
